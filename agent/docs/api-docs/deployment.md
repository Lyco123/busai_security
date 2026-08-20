# Agent Service 部署架构说明

## 概述

Agent服务部署在Cloudflare Workers上，可以与Cloudflare Pages联合部署，实现API服务和前端页面共享同一个域名。

## 部署架构

### 架构图

```
┌─────────────────────────────────────────┐
│     Cloudflare Edge Network            │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  自定义域名 (yourdomain.com)    │  │
│  └──────────────────────────────────┘  │
│              │                          │
│              ▼                          │
│  ┌──────────────────────────────────┐  │
│  │     路由分发 (Routing)            │  │
│  └──────────────────────────────────┘  │
│         │              │                │
│         ▼              ▼                │
│  ┌──────────┐    ┌──────────────┐     │
│  │  Worker  │    │    Pages     │     │
│  │  (API)   │    │  (Frontend)  │     │
│  └──────────┘    └──────────────┘     │
│       │                │                │
│       └────────────────┘                │
│              │                          │
│              ▼                          │
│      ┌───────────────┐                 │
│      │  D1 Database  │                 │
│      └───────────────┘                 │
└─────────────────────────────────────────┘
```

### 路由规则

| 路径 | 处理方式 | 说明 |
|------|---------|------|
| `/api/agent/*` | Worker处理 | API接口请求 |
| `/` 及其他路径 | Pages处理 | 前端静态文件或Pages Functions |

## 部署方式

### 方式1：Worker独立部署（当前方式）

Worker作为独立服务运行，部署地址为：
```
https://bus-agent.{account}.workers.dev
```

**特点**：
- Worker处理所有请求
- 非API路径返回404
- 适合纯API服务场景

**部署命令**：
```bash
cd agent
wrangler deploy
```

### 方式2：Worker + Pages联合部署（推荐）

Worker和Pages部署在同一个自定义域名下，通过路径前缀区分。

**部署地址**：
```
https://yourdomain.com
```

**路由逻辑**：
- `/api/agent/*` → Worker处理（API接口）
- 其他路径 → Pages处理（前端页面）

**配置步骤**：

1. **部署Worker**：
```bash
cd agent
wrangler deploy
```

2. **配置Pages路由**：
在Cloudflare Dashboard中，将Worker绑定到Pages项目：
- Pages项目 → Settings → Functions
- 添加路由规则：`/api/agent/*` → Worker

3. **或者使用wrangler.toml配置**：
```toml
# wrangler.toml
name = "bus-agent"
main = "src/index.ts"

# 如果使用自定义域名
routes = [
  { pattern = "yourdomain.com/api/agent/*", zone_name = "yourdomain.com" }
]
```

## 代码实现

### 路由处理逻辑

当前代码已经实现了路由分离：

```typescript
async function handleRequest(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const pathname = url.pathname.replace(/\/+$/, '');

  // API路由：处理 /api/agent/* 路径
  if (pathname.startsWith(API_PREFIX)) {
    const relativePath = pathname.slice(API_PREFIX.length) || '/';
    return handleAPIRequest(request, env, relativePath);
  }

  // 非API路径：fallback到Pages
  // 在Cloudflare Pages中，静态文件会自动处理
  return new Response('Not Found', { status: 404 });
}
```

### 关键点

1. **路径前缀检查**：只处理 `/api/agent/*` 路径
2. **非API路径**：返回404，让Pages处理（如果配置了Pages）
3. **CORS支持**：所有响应都包含CORS头，支持跨域请求

## 访问地址

### 开发环境

```bash
# 本地开发
wrangler dev

# 访问地址
http://localhost:8787/api/agent/health
```

### 生产环境

#### Worker独立部署
```
https://bus-agent.{account}.workers.dev/api/agent/health
```

#### Worker + Pages联合部署
```
https://yourdomain.com/api/agent/health
```

## 环境变量配置

在Cloudflare Dashboard或wrangler.toml中配置：

```toml
[vars]
OPENAI_API_KEY = "your-api-key"
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_ROUTER_MODEL = "gpt-4o-mini"
OPENAI_WORKER_MODEL = "gpt-4o-mini"
```

## 注意事项

1. **Worker和Pages共享域名**：需要确保路由规则正确配置
2. **CORS配置**：API接口已包含CORS头，支持跨域请求
3. **数据库访问**：Worker和Pages都可以访问D1数据库（如果配置了）
4. **性能**：Worker和Pages都在Cloudflare Edge Network上运行，延迟低

## 常见问题

### Q: Worker和Pages可以共享数据库吗？

A: 可以。如果Pages也配置了D1数据库绑定，两者可以访问同一个数据库。

### Q: 如何测试API接口？

A: 使用curl或Postman：
```bash
curl https://yourdomain.com/api/agent/health
```

### Q: 前端如何调用API？

A: 如果部署在同一域名下，使用相对路径：
```javascript
fetch('/api/agent/sessions')
```

如果Worker独立部署，使用完整URL：
```javascript
fetch('https://bus-agent.{account}.workers.dev/api/agent/sessions')
```

## 参考文档

- [Cloudflare Workers文档](https://developers.cloudflare.com/workers/)
- [Cloudflare Pages Functions](https://developers.cloudflare.com/pages/platform/functions/)
- [Worker路由配置](https://developers.cloudflare.com/workers/configuration/routing/)

