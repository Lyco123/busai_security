# Prompt Inventory

## Router

- `agent/skills/router/SKILL.md`: main router behavior and business path boundaries.
- `agent/src/domains/chat/router-prompts.ts`: runtime supplements, rule match prompt rendering, router context snippets.
- `agent/src/domains/chat/router-tools.ts`: router tool descriptions and schemas.
- `agent/src/domains/chat/router-tool-validation.ts`: validation and retry/clarification prompts.

## Conversational Skills

- `agent/skills/conversational/omni/SKILL.md`
- `agent/skills/conversational/driver_expert/SKILL.md`
- `agent/skills/conversational/vehicle_expert/SKILL.md`
- `agent/skills/conversational/unit_expert/SKILL.md`
- `agent/skills/conversational/route_expert/SKILL.md`
- `agent/skills/conversational/station_expert/SKILL.md`
- `agent/skills/conversational/incident_expert/SKILL.md`
- `agent/skills/conversational/rule_asker/SKILL.md`
- `agent/skills/conversational/rule_reply/SKILL.md`

## Structured Skills

- `agent/skills/structured/generate_driver_report/SKILL.md`
- `agent/skills/structured/generate_vehicle_report/SKILL.md`
- `agent/skills/structured/generate_unit_report/SKILL.md`
- `agent/skills/structured/generate_route_report/SKILL.md`
- `agent/skills/structured/generate_station_report/SKILL.md`
- `agent/skills/structured/generate_accident_investigation_report/SKILL.md`
- `agent/skills/structured/rule_builder/SKILL.md`

## Runtime Prompt Helpers

- `agent/src/domains/chat/vehicle-expert-prompts.ts`: expert deep COT system prompt prefixes.
- `agent/src/domains/chat/server-time-context.ts`: server time context.
- `agent/src/domains/chat/omni-kb-context.ts`: KB context prompt helper.
- `agent/src/shared/entity-alias-resolver.ts`: alias hint injection.

## Talk Tracks and Templates

- `agent/docs/话术/驾驶员画像 AI 通用话术_（20260305）.md`
- `agent/docs/话术/车辆画像 AI 通用话术（20260305） .md`
- `agent/docs/话术/线路画像 AI 通用话术（20260305）.md`
- `agent/docs/话术/单位画像 AI 通用话术（20260409）.md`
- `agent/docs/话术/事故分析报告模板.md`
- `agent/docs/话术/事故分析报告模板new0601.md`

## Ownership Rules

- Business routing boundaries belong in router skill and router tool descriptions.
- Worker output behavior belongs in worker skill files.
- Current-turn state belongs in runtime prompt supplements.
- Source/data availability belongs in tool descriptions, data source code, and report runtime config.
- Do not duplicate long business boundary tables in runtime snippets.

## Gaps

- There is no generated prompt catalog with file hash, owner, affected tests, and consuming code path.
- Some historical prompt material has encoding issues and should be normalized before official reuse.
