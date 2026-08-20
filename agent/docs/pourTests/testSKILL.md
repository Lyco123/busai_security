---
name: ai-assistant-playwright-test
description: Guides Claude Code (with Qwen 3.5 backend) to perform Playwright-based automated testing of the AI assistant section. Use when testing the assistant UI, chat flows, session management, or when the user asks for E2E tests of the AI assistant.
---

# AI 助手 Playwright 自动化测试 Skill

本 Skill 指导使用 **千问 3.5 作为后端的 Claude Code**，通过 **Playwright** 对本项目 **AI 助手板块**进行自动化测试。

- **测试原则与流程**：见 [test.md](test.md)
- **Playwright / 浏览器操作**：见 Playwright MCP

---

## 一、项目与入口

| 项目 | 路径 | 说明 |
|------|------|------|
| 前端 | `frtend-tsx/` | Vite + React，默认端口 5174 |
| AI 助手页面 | `/assistant` | 路由在 `App.tsx`，组件 `AIAssistant.tsx` |
| Agent API | `/api/agent` | 代理到 `VITE_AGENT_PROXY_TARGET`（默认 8787） |

**启动顺序**：先启动 agent 后端，再启动前端 `npm run dev`。

## 二、AI 助手核心元素与选择器

基于 `AIAssistant.tsx` 结构，常用选择器：

| 功能 | 选择器建议 | 说明 |
|------|------------|------|
| 新建对话 | `button:has-text("新建对话")` | 主操作按钮 |
| 消息输入框 | `textarea[placeholder*="输入消息"]` | 输入区域 |
| 发送按钮 | `button:has-text("发送")` | 发送消息 |
| 会话列表项 | `[role="button"]` 在侧边栏 | 可点击切换会话 |
| 加载中 | `text=加载中...` | 加载状态 |
| 暂无消息 | `text=暂无消息` | 空会话 |
| 错误提示 | `.text-rose-700` | 连接错误等 |
| 实验信息卡 | `text=车辆专家 CoT 开关实验` | 展示当前实验说明与会话分组状态 |

**流式回复**：助手回复为流式，需等待「正在生成...」消失后再断言。

## 三、推荐测试用例（本项目）

- **主流程**：进入 `/assistant` → 新建对话 → 输入消息 → 发送 → 等待回复完成 → 断言至少一条 user + 一条 assistant

- **多轮对话**：发送第一条消息并等待回复 → 发送第二条消息 → 等待回复 → 断言消息顺序与上下文

- **会话管理**：新建会话并发送消息 → 再新建会话 → 切换回第一个会话 → 删除一个会话 → 断言列表更新

- **异常与边界**：未登录访问、空输入、网络异常、流式回复等待

## 四、注意事项

1. **Agent 后端必须运行**：测试前确认 agent 服务（默认 8787）已启动。
2. **流式回复**：需等待「正在生成...」消失后再断言。
3. **认证**：若需登录，在测试中完成登录或注入 storageState。
4. **不依赖测试模式**：如无说明，不检查或管理「测试模式」相关代码。
