# Agent 测试方案归档说明

当前车辆专家路由实验已经结束，现网主干已固定为车辆专家优先路由：

- 车辆本体故障、报警、维修排查、车况诊断、是否可继续运营等问题，优先走 `consult_vehicle_expert`
- 通用咨询、制度说明、跨主题总结等问题，继续走 `consult_omni`
- 报告生成、规则回复等其他链路保持原有路由机制

原测试方案与实验脚本说明已归档到 `docs/legacy/`：

- `docs/legacy/Agent测试迭代方案-router-skill-ab.md`
- `docs/legacy/车辆专家拆分AB测试方案.md`
- `docs/legacy/车辆专家CoT开关AB测试方案.md`
- `docs/legacy/assistant-ab-playwright.md`
- `docs/legacy/router-ab-x.SKILL.md`
- `docs/legacy/router-ab-y.SKILL.md`

后续如需继续做新实验，应直接复用现有 `ab-test` infra。当前在用的实验方案为 `docs/legacy/车辆专家CoT开关AB测试方案.md`，不再沿用旧的 Router 拆分盲测方案。
