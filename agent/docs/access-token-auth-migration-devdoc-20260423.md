# Access Token 鉴权迁移简要 DevDoc

## 1. 背景

当前 Agent 系统已具备基础认证与会话隔离能力：

- Agent 前端/接口侧通过 `bus_anon_id`（匿名用户标识）、`bus_auth_token` 识别匿名态与登录态
- Agent 内部通过 `principal_id` 和 `agent_sessions.owner_id` 做 session 数据隔离
- 下游 MCP 服务已定义 `X-Access-Token`、`X-Transparent-Para` 作为统一身份与透传上下文

现状适合开发联调与局部闭环，但不适合作为生产主鉴权体系。未来生产环境需要与现有统一账号/鉴权系统对齐，因此主身份识别应迁移为基于 `access token` 的鉴权模式。

## 2. 当前问题

### 2.1 主身份源分裂

- Agent 本地维护 `agent_users`、`agent_auth_sessions`
- MCP/其他内部服务依赖统一 `X-Access-Token`
- 同一用户在 Agent 与下游服务中的身份来源不一致

### 2.2 权限口径不统一

- Agent 当前主要依据本地 Cookie session 决定身份
- 下游服务依据透传 token 或内部头决定权限
- 后续组织、角色、租户、数据域容易出现多套映射

### 2.3 Agent 承担了不该承担的账号职责

- 本地用户名/密码登录更像联调方案
- Agent 应作为统一鉴权体系的消费方，而不是账号主系统

## 3. 目标

将 Agent 体系调整为：

- `access token` 作为全链路主身份凭证
- Agent 负责消费、校验、解析和透传 token
- Agent session 仅承担业务会话职责，不再承担主鉴权职责
- 下游 MCP / KB / 其他内部服务与 Agent 使用同一身份口径

一句话概括：

> 统一账号系统负责“你是谁”，Agent session 体系负责“你这次聊了什么”。

## 4. 目标架构

### 4.1 身份链路

1. 用户通过统一鉴权系统登录
2. 前端持有统一 `access token`
3. 请求 Agent 时携带 `Authorization: Bearer <token>` 或约定头
4. Agent 校验并解析 token，生成统一 `AuthContext`
5. Agent 将身份信息透传给 MCP / KB 等内部服务
6. 各服务依据同一身份语义做授权与审计

### 4.2 Agent 内部职责

- 保留 session 管理、消息存储、会话归属
- 不再作为主账号系统
- 不再以本地用户名密码作为生产主登录路径

## 5. 建议的数据与上下文模型

Agent 内部统一收敛到一个运行时鉴权上下文：

```ts
type AuthContext = {
  user_id: string;
  user_name?: string;
  tenant_id?: string;
  org_id?: string;
  org_code?: string;
  roles: string[];
  access_token: string;
  source: 'access_token' | 'compat_cookie';
};
```

建议保留 `principal_id`，但只作为 Agent 内部兼容键，由统一身份派生，例如：

```ts
principal_id = `user:${user_id}`;
```

如后续租户隔离要求更强，可升级为：

```ts
principal_id = `tenant:${tenant_id}:user:${user_id}`;
```

## 6. Session 体系定位

迁移后 session 体系继续保留，但职责收敛为：

- 会话列表与详情归属
- 对话历史隔离
- 规则配置、研究评估等业务上下文挂载

不再承担：

- 主账号认证
- 主登录态签发
- 全系统统一权限来源

## 7. 迁移策略

### 阶段 1：接入统一 token

- Agent 新增 `access token` 解析能力
- 优先从请求头解析身份
- 旧 Cookie 登录方案暂时保留，用于兼容现有前端和测试链路

### 阶段 2：双栈收敛

- 所有 handler / repository / proxy 统一只消费 `AuthContext`
- 禁止各模块分别直接读取 Cookie 或自定义头
- MCP / KB 透传字段统一规范

### 阶段 3：下线本地账号体系

在前端和网关完成迁移后，下线以下内容作为生产主链路：

- `/auth/login`
- `agent_users`
- `agent_auth_sessions`
- `bus_auth_token` 作为主登录态

如需匿名体验，可单独保留 `bus_anon_id`；如生产不允许匿名，可一并移除。

## 8. 接口与透传建议

### 8.1 主身份凭证

- 推荐：`Authorization: Bearer <access_token>`
- 如历史系统已有固定头，也可兼容，但内部应统一映射为同一个 `AuthContext`

### 8.2 透传上下文

`X-Transparent-Para` 仅承担辅助审计与链路上下文，建议固定字段：

- `userId`
- `userName`
- `orgId`
- `orgCode`
- `requestTime`
- `requestId`
- `traceId`

该头不应单独作为主授权依据。

## 9. 对现有代码的改造重点

优先改造以下位置：

- `src/infra/auth/session-store.ts`
  - 从“Cookie + 本地表”升级为“优先 access token，Cookie 仅兼容”
- `src/app/http-router.ts`
  - 全入口统一基于新 `AuthContext` 分发
- `src/domains/sessions/repository.ts`
  - 继续使用 `owner_id`，但 owner 来源改为统一身份派生结果
- `src/infra/kb-proxy.ts`
  - 与下游服务保持统一身份透传口径

## 10. 非目标

本次迁移不包含：

- 重做 session 业务模型
- 重做 chat / router / rules / research 业务流程
- 重做 MCP 服务自身的权限模型

本次只解决“身份来源统一、授权口径统一、会话职责收敛”。

## 11. 结论

生产环境的正确边界应为：

- 统一鉴权系统负责账号、登录、token 签发
- Agent 负责 token 消费、业务会话、下游透传
- MCP / KB / 内部服务负责基于统一身份继续做业务权限控制

这能避免 Agent 演变成另一套账号系统，同时保留现有 session 体系作为业务会话层的价值。
