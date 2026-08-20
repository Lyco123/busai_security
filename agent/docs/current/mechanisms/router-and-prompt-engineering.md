# Router and Prompt Engineering

## Ownership Model

Prompt behavior is split across four locations:

- Router skill: main business routing boundary.
- Router tool descriptions: tool capability and selection constraints.
- Runtime prompt supplements: current-turn context, rule match context, latest report context, pending clarification context.
- Worker skills: task-specific answer/report behavior.

Primary files:

- `agent/skills/router/SKILL.md`
- `agent/src/domains/chat/router-prompts.ts`
- `agent/src/domains/chat/router-tools.ts`
- `agent/src/domains/chat/router-tool-validation.ts`
- `agent/src/domains/chat/router-service.ts`
- `agent/skills/conversational/**/SKILL.md`
- `agent/skills/structured/**/SKILL.md`

## Router Rule

Router should answer one question: which path should handle this turn?

Valid outcomes include:

- consult an expert
- generate a report
- reply through rule flow
- ask for missing information
- handle unsupported/out-of-scope cases

Router should not become the main business answer generator.

## Prompt Injection Points

Runtime context can include:

- rule match results
- rule routing policy
- latest structured report context
- structured report failure context
- pending clarification context
- server time context
- history summaries
- dynamic tool allow list

These injections should explain current state, not duplicate long business boundaries already owned by skills and tool descriptions.

## Tool Validation

`router-tool-validation.ts` validates router tool calls and can produce:

- accepted dispatch
- missing parameter prompt
- retry prompt for router
- clarification request
- fallback behavior

Validation is part of prompt engineering because it shapes the next router prompt and prevents invalid worker calls.

## Known Sensitive Areas

- Latest report continuation versus new report request.
- Pending clarification recovery versus new topic.
- Rule high-score match versus normal consultation.
- Dynamic tool allow list trimming.
- No-tool router fallback to omni-style answer.
- Entity normalization, especially route numbers, plate formats, unit aliases, and duplicate names.

## Historical Sources

- `agent/docs/router-prompt-followups-20260416.md`
- `agent/docs/router-shortcut-removal-20260408.md`
- `agent/docs/router-optimization-20260518.md`
- `agent/docs/omni-router-eval-findings-20260316.md`
- `agent/docs/non-report-pipeline-prompt-injection-map.md`
- `agent/docs/report-pipeline-prompt-injection-map.md`

## Gaps

- Entity resolution should become a shared `extract -> normalize -> expand -> match -> select` pipeline. Current code still has domain-specific lookup and normalizer behavior.
- Prompt ownership is documented here, but not enforced by tooling. A prompt inventory checker would help prevent duplicated business boundaries.
