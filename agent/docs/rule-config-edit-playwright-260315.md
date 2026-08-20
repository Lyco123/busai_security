# RuleConfig 编辑态 Playwright 测试矩阵 260315

## 目标
验证 `rule_asker -> rule_builder -> saveRuleConfigSessionV2` 在**编辑已有规则**时，是否能正确处理以下三类高频业务输入：

- 多轮对话信息分散
- 信息不全 / 抽象诉求
- 信息冲突

## 基线业务规则
1. 证件到期提醒
2. 车辆出库前故障上报
3. 恶劣天气停运解释
4. 失物现金上交流程
5. 驾驶员培训记录查询

## 用例矩阵
每条规则各跑 3 条编辑用例，共 15 条。

### A. 多轮对话信息分散
- 先改触发场景，再补一条关键点，再补一条 required_info，再改语气
- 期望：
  - 新场景被保留
  - “补上 / 增加”表达表现为追加，不覆盖原有关键点或必填信息
  - 依赖 `match_text` 的 `examples` / `template` / `safe_defaults` 不应停留在旧场景

### B. 信息不全 / 抽象诉求
- 只给“更适合早班司机”“再严谨些”“更像客服口径”这类编辑意图
- 期望：
  - 不应擅自映射到 `tone` 或其它字段
  - 应进入澄清态而不是直接可确认
  - UI 不应给出错误的“规则已可确认”

### C. 信息冲突
- 同一轮同时出现互相矛盾的要求，例如“可以继续出车”与“不要建议继续带病出车”
- 期望：
  - 先指出冲突并提 1 个澄清问题
  - 不应把冲突内容直接写入草稿
  - `rule_builder` 遇到未解决冲突时应返回 `needs_rework` / `blocked_conflict`

## 本轮迭代关注的问题
1. 编辑态基线规则本身完整，导致无 patch 的澄清轮次仍被推成 `awaiting_confirm`
2. `rule_asker` 对“更适合某类人”“再细一点”这类抽象诉求过度猜测
3. “补上 / 增加”型编辑把数组字段整体覆盖
4. `rule_builder` 对旧 `examples` / `template` / `safe_defaults` 的陈旧场景刷新不足
5. `reply_goal` / `key_points` 与 `do_not_say` 的内部冲突没有被返工拦住

## 迭代策略
1. 在 `rule_asker` 中强化编辑态规则：
   - 明确区分追加和替换
   - 抽象编辑意图必须先澄清
   - 冲突轮次必须产出 `missing_fields_guess`
2. 在 V2 状态机中消费 `missing_fields_guess`：
   - 只要本轮仍需澄清，就保持 `collecting`
   - 避免完整旧草稿把澄清轮次误推成 `awaiting_confirm`
3. 在 `rule_builder` 中强化上下文编译：
   - 使用 `draft_mode`、`latest_user_request`、`conversation_context`
   - 对追加型编辑保留旧要点并追加新要点
   - 新场景出现时刷新低风险依赖字段
   - 检测内部冲突并返工
