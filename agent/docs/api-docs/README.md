# Agent Service API 接口文档

## 文档说明

本文档目录包含 Agent Service 的 REST API 接口文档，使用 LaTeX 格式编写。

## 文件说明

- `api-reference.tex` - 完整的 API 接口文档（LaTeX 源码）
- `README.md` - 本说明文件

## 文档内容

文档包含以下章节：

1. **概述** - API 基础信息和版本
2. **通用规范** - 请求/响应格式、状态码等
3. **接口列表** - 详细的接口说明
   - 系统接口（健康检查、工具列表）
   - 会话管理（创建、查询、删除）
   - 对话接口（发送消息、流式对话）
4. **数据模型** - 数据结构定义
5. **使用示例** - 代码示例
6. **错误处理** - 错误码和错误处理
7. **最佳实践** - 使用建议
8. **附录** - 工具说明和变更日志

## 接口概览

### 系统接口
- `GET /api/agent/health` - 健康检查
- `GET /api/agent/tools` - 获取工具列表

### 会话管理
- `GET /api/agent/sessions` - 获取会话列表
- `POST /api/agent/sessions` - 创建会话
- `GET /api/agent/sessions/{id}` - 获取会话详情
- `DELETE /api/agent/sessions/{id}` - 删除会话

### 对话接口
- `POST /api/agent/chat` - 发送消息（非流式）
- `POST /api/agent/chat/stream` - 发送消息（流式，SSE）

## 查看文档

由于文档使用 LaTeX 格式，如需查看编译后的 PDF，需要：

1. 安装 LaTeX 发行版（如 TeX Live、MiKTeX）
2. 编译文档：
   ```bash
   xelatex api-reference.tex
   # 或
   pdflatex api-reference.tex
   ```

**注意**：根据要求，文档不需要编译，可以直接查看 `.tex` 源文件。LaTeX 源文件具有良好的可读性，可以直接阅读。

## 快速参考

### 基础路径
```
/api/agent
```

### 请求格式
```http
Content-Type: application/json
Accept: application/json
```

### 响应格式
所有响应均为 JSON 格式。

### 状态码
- `200` - 成功
- `201` - 创建成功
- `400` - 请求参数错误
- `404` - 资源不存在
- `500` - 服务器内部错误

## 更新日志

- 2024-01-15: 初始版本，包含所有基础接口文档

