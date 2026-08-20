# 评估：为 rule_builder 增加对话上下文的影响

## 当前实现

- **Builder 输入**：仅接收 `rule_draft` JSON 对象
- **可获取的上下文**：通过 `getAgentSession(db, sessionId)` 可获取完整对话记录

## 潜在收益

1. **理解用户真实意图**：对话中的业务背景和隐含需求，有助于生成更准确的规则
2. **补充缺失字段**：从对话中提取线索，提高字段补全质量
3. **识别隐含约束**：用户提到的"不要承诺"等约束可补充到 `do_not_say`
4. **优化 examples 生成**：从对话中提取更多真实表达方式

## 潜在风险

1. **上下文噪音**：可能包含无关信息或用户反复修改的过程
2. **Token 成本增加**：约 2-5 倍（从 ~1000 tokens 增至 ~3000-5000 tokens）
3. **性能影响**：需要额外查询数据库，增加 ~50-200ms 延迟
4. **一致性风险**：对话历史可能包含用户修改过程，Builder 可能混淆

## 推荐方案：智能提取 + 可选开关

### 实现策略

```typescript
function extractRuleConfigContext(messages: AgentMessage[]): string {
  // 1. 找到规则配置开始的消息（通过 metadata.rule_config 判断）
  const configStartIndex = messages.findIndex(
    msg => msg.metadata?.rule_config?.status === 'collecting'
  );
  if (configStartIndex === -1) return '';
  
  // 2. 提取配置相关的消息（从开始到确认前）
  const configMessages = messages.slice(configStartIndex);
  const configEndIndex = configMessages.findIndex(
    msg => msg.metadata?.rule_config?.status === 'ready_for_confirm'
  );
  const relevantMessages = configEndIndex > 0 
    ? configMessages.slice(0, configEndIndex + 1)
    : configMessages;
  
  // 3. 只保留 user 和 assistant 的对话，限制长度
  const filtered = relevantMessages
    .filter(msg => msg.role === 'user' || msg.role === 'assistant')
    .slice(-20); // 最多 20 轮对话
  
  return filtered.map(msg => 
    `${msg.role === 'user' ? '用户' : '助手'}: ${msg.content}`
  ).join('\n\n');
}
```

### 成本控制

- 限制提取范围：只提取规则配置相关的对话
- 限制长度：最多 20 轮对话，约 1000-2000 tokens
- 可选启用：默认关闭，需要时开启

## 预期效果

- **质量提升**：字段补全准确性 +15-25%，规则安全性 +10-20%
- **成本增加**：Token 成本 +50-100%，延迟 +50-200ms
- **ROI**：在复杂规则配置场景下价值较高

## 结论

✅ **建议实施，采用渐进式方案**

1. **短期**：实现智能提取，默认关闭，通过配置开关控制
2. **中期**：收集使用数据，评估效果，优化提取策略
3. **长期**：根据效果决定是否默认启用

### 风险控制

- 设置 Token 上限（如 2000 tokens）
- 提供降级机制（上下文获取失败时回退到当前方案）
- 监控成本和使用情况
