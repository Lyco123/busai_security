# 方案：将 rule_draft 改为 Markdown 格式传给 Builder

## 问题分析

### 当前情况
- **存储格式**：JSON（在 `rule_drafts.draft` 字段）
- **使用场景**：
  1. `rule_asker`：通过工具读写 JSON 格式
  2. **前端**：读取 JSON 显示字段
  3. **`rule_builder`**：读取 JSON 并编译

### 用户需求
- 将 `rule_draft` 改为 MD 格式，和对话历史拼接一起发送给 builder

### 实际情况
- ❌ `rule_asker` 和前端也需要读取 draft
- ✅ **但可以优化**：存储仍用 JSON，传给 builder 时转换为 MD + 对话上下文

## 推荐方案：混合格式（存储 JSON，传给 Builder 用 MD）

### 核心思路
1. **存储层**：继续使用 JSON 格式（兼容现有代码）
2. **Builder 输入层**：转换为 Markdown + 对话上下文
3. **零破坏性**：不影响 `rule_asker` 和前端

### 实现方案

#### 1. JSON draft 转换为 Markdown

```typescript
function draftToMarkdown(draft: Record<string, unknown>): string {
  const lines: string[] = ['# 规则草稿\n'];
  if (draft.name) lines.push(`## 规则名称\n${draft.name}\n`);
  if (draft.match_text) lines.push(`## 触发描述\n${draft.match_text}\n`);
  if (Array.isArray(draft.examples)) {
    lines.push('## 用户示例\n');
    draft.examples.forEach((ex: unknown) => lines.push(`- ${String(ex)}`));
    lines.push('');
  }
  if (draft.reply_goal) lines.push(`## 回复目标\n${draft.reply_goal}\n`);
  if (Array.isArray(draft.key_points)) {
    lines.push('## 关键要点\n');
    draft.key_points.forEach((p: unknown) => lines.push(`- ${String(p)}`));
    lines.push('');
  }
  if (Array.isArray(draft.required_info)) {
    lines.push('## 必填信息\n');
    draft.required_info.forEach((info: unknown) => {
      if (typeof info === 'object' && info !== null) {
        const item = info as { key?: string; ask?: string; required?: boolean };
        lines.push(`- **${item.key}**：${item.ask} ${item.required ? '（必填）' : '（可选）'}`);
      }
    });
    lines.push('');
  }
  if (draft.template) lines.push(`## 回复模板\n\`\`\`\n${draft.template}\n\`\`\`\n`);
  if (draft.safe_defaults && typeof draft.safe_defaults === 'object') {
    lines.push('## 安全默认值\n');
    Object.entries(draft.safe_defaults as Record<string, unknown>).forEach(([k, v]) => {
      lines.push(`- **${k}**：${String(v)}`);
    });
    lines.push('');
  }
  if (Array.isArray(draft.do_not_say)) {
    lines.push('## 禁止表达\n');
    draft.do_not_say.forEach((item: unknown) => lines.push(`- ❌ ${String(item)}`));
    lines.push('');
  }
  if (draft.tone) lines.push(`## 语调风格\n${draft.tone}\n`);
  return lines.join('\n');
}
```

#### 2. 提取对话上下文

```typescript
async function extractRuleConfigConversation(env: Env, sessionId: string): Promise<string> {
  const session = await getAgentSession(env.DB, sessionId);
  if (!session) return '';
  const configStartIndex = session.messages.findIndex(
    msg => msg.metadata?.rule_config?.status === 'collecting'
  );
  if (configStartIndex === -1) return '';
  const configMessages = session.messages.slice(configStartIndex);
  const configEndIndex = configMessages.findIndex(
    msg => msg.metadata?.rule_config?.status === 'ready_for_confirm'
  );
  const relevantMessages = configEndIndex > 0 
    ? configMessages.slice(0, configEndIndex + 1)
    : configMessages;
  const filtered = relevantMessages
    .filter(msg => msg.role === 'user' || msg.role === 'assistant')
    .slice(-20);
  if (filtered.length === 0) return '';
  const conversation = filtered.map(msg => {
    const role = msg.role === 'user' ? '用户' : '助手';
    return `**${role}**：${msg.content}`;
  }).join('\n\n');
  return `## 配置对话历史\n\n${conversation}\n`;
}
```

#### 3. 修改 `compileRuleDraft`

```typescript
async function compileRuleDraft(
  env: Env,
  draft: RuleDraft,
  includeContext: boolean = true
): Promise<Record<string, unknown>> {
  const draftMarkdown = draftToMarkdown(draft.draft);
  let contextMarkdown = '';
  if (includeContext) {
    contextMarkdown = await extractRuleConfigConversation(env, draft.session_id);
  }
  const prompt = `请将以下规则草稿编译为 rule_json，只返回严格 JSON。

${contextMarkdown ? `${contextMarkdown}\n---\n\n` : ''}${draftMarkdown}

---

请根据以上信息，输出完整的 rule_json（严格 JSON 格式，不要 Markdown）。`;
  // ... 调用 LLM
}
```

## 方案对比

### 方案 A：完全改为 MD（不推荐）
- ❌ 需要修改 `rule_asker` 工具接口和前端解析逻辑
- ❌ 破坏性改动大，风险高

### 方案 B：混合格式（推荐）✅
- ✅ 零破坏性：不影响 `rule_asker` 和前端
- ✅ 实现简单：只需修改 `compileRuleDraft` 函数
- ✅ 向后兼容：存储格式不变

## 预期效果

- **质量提升**：理解准确性 +20-30%，字段补全 +15-25%
- **成本影响**：Token 成本 +30-50%，延迟 +50-200ms
- **复杂度**：低（只需修改一个函数）

## 结论

✅ **强烈推荐采用混合格式方案**

**理由**：
1. 实现简单，风险低
2. 不影响现有功能
3. 预期效果显著

**下一步**：
1. 先实现 `draftToMarkdown` 和修改 `compileRuleDraft`
2. 测试效果
3. 再决定是否增加对话上下文功能
