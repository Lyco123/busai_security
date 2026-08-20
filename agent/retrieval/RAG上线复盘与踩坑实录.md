# RAG 上线复盘与踩坑实录

日期：`2026-03-31`

先说结论：

- RAG 检索服务已经在测试环境上线
- 主链路已经打通：`cloudflared -> retrieval -> Worker 代理 -> 前端`
- 当前阶段不再是“能不能拉起来”，而是“上线后继续迭代”

这份文档记录的是这次从排查、修复到恢复可用的全过程。写下来主要有两个目的：

- 后面再遇到同类问题，能少走点弯路
- 新同事接手时，不至于从一堆日志里考古

## 1. 最终状态

目前已经确认正常的能力：

- `kb-api` 正常启动
- `kb-worker` 正常启动
- Qdrant 正常运行
- 外部 ClickHouse 已打通
- `busodemo-kb-api.canocache.com` 可访问
- Worker 通过 `KB_API_BASE_URL` 转发知识库请求可用
- `GET /v1/documents` 正常
- `POST /v1/retrieve` 正常
- `POST /v1/documents/preview` 正常

一句话概括当前状态：

`RAG 服务已上线，进入迭代阶段。`

## 2. 这次到底卡了什么

### 2.1 一开始像是“哪都不对”

最早看到的现象很散：

- 前端知识库页面报错
- `kb-worker` 反复重启
- 检索接口报 500
- 上传 preview 也报 500

这种时候最容易犯的错是同时怀疑所有环节：

- tunnel
- Worker
- 前端
- embedding
- 数据库

结果最后证明，前面几轮主要还是基础配置和兼容性问题叠在一起，不是某一个点单独炸了。

### 2.2 第一个坑：compose 文件用错了

测试服务器本身已经有 ClickHouse，但最开始用了默认的 `docker-compose.yml`。

这个文件会额外起一个 `kb-clickhouse`，于是直接撞上宿主机的 `8123` 端口。

结果就是：

- 容器起了一半
- 端口冲突
- 现场看起来像“服务在跑，但又没完全跑”

最后确认，这台测试服必须用：

```bash
docker compose -f docker-compose.server.yml ...
```

这个坑很朴素，但很伤时间。

### 2.3 第二个坑：客户给的是 9000，但我们实际用的是 8123

客户给的 ClickHouse 信息里，端口是 `9000`。  
但当前 retrieval 用的是 HTTP DSN，不是 native 驱动。

也就是说，实际要配的是：

```env
CK_DSN=http://default:<url-encoded-password>@host.docker.internal:8123
```

不是：

- `9000`
- 也不是直接把密码原样往 URL 里塞

密码里有 `@` 的话，还得编码成 `%40`。

最后可用配置是：

```env
CK_DSN=http://default:Zhongda%4084@host.docker.internal:8123
```

### 2.4 第三个坑：改了 `.env`，结果容器根本没吃到

中间有一段时间，我们已经把 `.env` 改对了，但服务行为完全没变。

原因很简单：

```bash
docker compose restart
```

不会重载 `env_file`。

正确操作是：

```bash
docker compose -f docker-compose.server.yml up -d --force-recreate kb-api kb-worker
```

这个坑不复杂，但特别容易让人误判成“是不是配置没写对”。

### 2.5 第四个坑：库名看起来像是 `ai_security`，实际老表在 `default`

客户给了 `ai_security`，所以一开始自然想往这个库上配。

结果 worker 很快报：

- `ai_security.kb_index_jobs does not exist`

继续往下看才发现，老的知识库表实际是在 `default` 里。

所以这里不是权限问题，也不是初始化没做，而是连错库了。

最终改回：

- 先连 `default`
- 不在 `CK_DSN` 后面带 `/ai_security`

问题就往前推进了一大步。

### 2.6 第五个坑：外部 ClickHouse 版本比本地假设更老

等数据库连通以后，`retrieve` 还是报错。

报错位置集中在 ClickHouse 的查询语法上，尤其是这类写法：

```sql
FROM kb_clauses FINAL c
INNER JOIN kb_documents FINAL d
```

在本地环境没问题，但在测试服那台旧一点的 ClickHouse 上不行。

最后做的修复是：

- 把 `FINAL` 放进子查询
- 显式写出列名

也就是尽量把 SQL 写得保守一点，让老版本也能接受。

这一步之后，检索接口才真正从“语法错误”变成“业务逻辑继续往下跑”。

### 2.7 第六个坑：schema 是旧的，代码以为它是新的

语法兼容之后，又遇到缺列问题。

先是 `order_index` 不存在，后面又发现 `kb_documents` 里一些文件相关字段也没有，比如：

- `file_name`
- `file_mime`
- `file_size`
- `file_hash`
- `file_storage_key`

根因其实很常见：

- 老表早就存在
- `CREATE TABLE IF NOT EXISTS` 不会帮你补列

也就是说，`init-schema` 在这种情况下只会说“表在”，不会说“表还差东西”。

所以最后做了两件事：

1. 测试服上先手工补列
2. 代码里给 `init-schema` 增加兼容性补列逻辑

这样后面再跑初始化时，至少不会重复踩同一个坑。

### 2.8 第七个坑：没有 embedding key，检索不可能成功

中间有一次检索直接返回了 embedding 服务的 `401`。

日志里写得很明白：

- 没有提供 API key

这一步其实反而是好消息，因为说明：

- 检索代码已经跑到 embedding 请求这一步了
- 不是链路没通，而是配置没补齐

补上 `EMBEDDING_API_KEY` 后，这一层就过去了。

### 2.9 第八个坑：前端说“500”，实际未登录时先是 `403`

一开始前端知识库页报错，看起来像后端又 500 了。

后来直接打 Worker 的 `/api/agent/kb/*` 入口，才发现未带管理员登录态时返回的是：

```http
403 {"error":"forbidden"}
```

这个结果和代码一致。当前 `/kb/*` 代理就是只允许管理员。

也就是说，那一轮里前端看到的“异常”，并不全是后端挂了，其中一部分只是权限被拦住了。

这个区分很重要，不然后面会一直朝错方向查。

### 2.10 第九个坑：preview 最后卡在 `DateTime64`

真正最磨人的问题，最后落在 `POST /v1/documents/preview`。

现象是：

- 普通 `GET` 接口都通了
- 检索也能走到一定程度
- 但 preview 上传一发就 500

日志最后定位到 ClickHouse 在写 `expires_at` 时解析失败。  
问题不是字段本身，而是写入格式。

旧版 ClickHouse 不接受这种 ISO UTC 字符串：

```text
2026-03-30T17:31:55.866Z
```

于是代码里补了统一归一化：

- 插入前把时间转成 `YYYY-MM-DD HH:mm:ss.sss`

这一改完，preview 立刻恢复成 `200`。

到这里，上传链路才算真的打通。

### 2.11 第十个坑：本地代码修好了，不代表服务器已经跑上了

这个坑挺典型，也最容易被忽略。

本地代码已经修完，压缩包也打了，但服务器日志还是在报旧错误。  
最后检查发现，服务器上的 `src/db/clickhouse.ts` 还是旧版本。

原因不复杂：

- 包虽然上传了
- 但服务器目录没有真正覆盖干净

最后重新做了一遍：

- 本地重新打包
- `scp` 上传
- 服务器安装 `unzip`
- 删除旧目录
- 重新解压
- 重新 build/recreate

这之后新代码才真正生效。

这个教训很简单：

不要用“我已经传了包”替代“服务器现在正在跑新代码”。

## 3. 这次沉淀下来的改动

这次不是只在测试服手工修补，已经把关键兼容逻辑收进仓库了。

### 3.1 查询兼容

文件：

- `src/db/repository.ts`

处理内容：

- 检索相关的 `FINAL` 联表查询改成旧版 ClickHouse 更稳的写法
- 避免在老版本外部库上直接炸语法

### 3.2 老 schema 自动补列

文件：

- `src/db/repository.ts`
- `src/init-schema.ts`

处理内容：

- 初始化 schema 后，自动给老表补缺失列
- 重点补了 `order_index` 和文档文件元数据相关字段

### 3.3 `DateTime64` 插入兼容

文件：

- `src/db/clickhouse.ts`

处理内容：

- 所有 insert 在写入前先规范化 ISO UTC 时间串
- 避免旧版 ClickHouse 在 `JSONEachRow` 上解析失败

### 3.4 文档补齐

已补的文档：

- `README.md`
- `TEST_SERVER_RECOVERY.md`
- 本文档

## 4. 当前推荐部署方式

### 4.1 retrieval

测试服使用：

```bash
docker compose -f docker-compose.server.yml up -d --build --force-recreate
```

### 4.2 ClickHouse

使用 HTTP DSN：

```env
CK_DSN=http://default:<url-encoded-password>@host.docker.internal:8123
```

注意：

- 不是 `9000`
- 是 `8123`
- 密码如果有特殊字符，必须 URL 编码

### 4.3 对外访问

retrieval 域名：

- `https://busodemo-kb-api.canocache.com`

Worker 代理入口：

- `https://api.buso.canocache.com/api/agent/kb/*`

## 5. 这次最值得记住的几点

以后再排这类问题，建议按下面顺序来：

1. 先确认 compose 文件有没有用对
2. 先确认 `.env` 改完后是不是 `force-recreate`
3. 先确认 ClickHouse 走的是 `8123` HTTP
4. 先确认连的是不是对的库
5. 先确认服务器上跑的是不是真正的新代码
6. 先确认老 schema 有没有缺列
7. 先确认 embedding key 是否真的进了容器
8. 先分清楚 `403`、`500`、`502`
9. 先直连 retrieval，再看 Worker，再看前端

照这个顺序查，基本能少掉不少无效怀疑。

## 6. 后续迭代建议

既然已经上线，后面优先级就不再是“服务起不来怎么办”，而是下面这些：

### P1

- 跑通 `preview -> commit -> worker -> retrieve` 全链路回归
- 导入真实测试文档，验证向量检索命中效果
- 用管理员账号回归前端知识库管理页

### P2

- 调整 `/kb/*` 权限模型，支持“登录可读、管理员可写”
- 给关键失败路径补更清晰的错误提示
- 补测试服部署 SOP

### P3

- 对齐 Qdrant client/server 版本
- 补监控和告警
- 评估是继续兼容旧 ClickHouse，还是直接统一升级

## 7. 收尾

这次上线不是那种一条命令结束战斗的上线。  
更准确地说，是把一套已经基本成型的服务，按目标环境的实际情况重新顺了一遍。

好处是现在主链路已经跑通，后面可以把精力从“为什么又挂了”转到“怎么把它做得更稳、更顺手”。

最后再记一次结论：

`RAG 服务已上线，进入迭代阶段。`
