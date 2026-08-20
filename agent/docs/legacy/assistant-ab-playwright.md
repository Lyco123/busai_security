# Assistant A/B Playwright Test

运行入口：

```bash
cd agent
npm run test:assistant-ab-playwright
```

必填环境变量：

```bash
set ASSISTANT_USERNAME=1
set ASSISTANT_PASSWORD=111111
```

常用可选项：

```bash
set ASSISTANT_URL=https://busodemo.canocache.com/assistant
set ASSISTANT_API_BASE_URL=https://api.buso.canocache.com/api/agent
set ASSISTANT_HEADLESS=true
set ASSISTANT_ROUND=round1
set ASSISTANT_CASE_LIMIT=5
set ASSISTANT_CASE_FILTER=multi-
```

输出：

- 原始结果：`agent/test-results/assistant-ab/*.json`
- 汇总报告：`agent/test-results/assistant-ab/*.md`

`recommendation` 取值：

- `keep_y`: 建议保留并扩大 Y
- `partial_keep_y`: 建议按场景保留 Y
- `rollback_y`: 建议回退 Y

脚本行为：

- 用 Playwright 登录 `/assistant`
- 用同一浏览器会话下的 API 请求执行 X/Y 对照
- 记录 `ab_test`、`routing`、文本摘要、耗时、失败信息
- 运行结束后清理测试会话
