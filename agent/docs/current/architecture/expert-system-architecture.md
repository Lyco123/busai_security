# Expert System Architecture

## Purpose

The expert system separates consultation and formal report generation by domain. Router chooses a tool, expert registry maps that tool to a domain/task, and context builder adds domain runtime context before worker execution.

## Current Domains

The current registry has six domains:

- driver
- vehicle
- unit
- route
- station
- incident

Each domain has:

- `consult`: conversational expert answer.
- `report`: structured report generation, where supported.

## Main Components

```text
Router
  -> worker tool
  -> Expert Registry
  -> Context Builder
  -> Worker Runner
  -> Skill + tools + LLM
```

Primary files:

- `agent/src/domains/experts/registry.ts`
- `agent/src/domains/experts/context-builder.ts`
- `agent/src/domains/chat/worker-runner.ts`
- `agent/skills/conversational/*/SKILL.md`
- `agent/skills/structured/*/SKILL.md`

## Expert Registry

The registry defines:

- `domain`
- `taskType`
- `workerTool`
- `skillKey`
- whether deep COT prefix is supported
- context flags: `profile`, `kb`, `latestReport`, `pendingClarification`

Current worker tools include:

- `consult_driver_expert`, `generate_driver_report`
- `consult_vehicle_expert`, `generate_vehicle_report`
- `consult_unit_expert`, `generate_unit_report`
- `consult_route_expert`, `generate_route_report`
- `consult_station_expert`, `generate_station_report`
- `consult_incident_expert`, `generate_accident_investigation_report`

## Context Builder

The context builder centralizes extra runtime context. It prevents each expert from manually duplicating logic for:

- latest structured report context
- pending clarification context
- profile/report source context
- deep COT system prompt prefix
- future KB context expansion

## Design Rule

Router decides where a request goes. Expert workers execute one assigned responsibility. Business boundaries should be expressed in:

- router skill
- router tool descriptions
- expert skill files
- expert registry/context flags

They should not be duplicated in unrelated runtime prompt snippets.

## Historical Sources

- `agent/docs/expert-runtime-service-design-20260418.md`
- `agent/docs/weekly_reports/260422/md/agent开发周报260422.md`
- `agent/docs/weekly_reports/260513/md/agent开发周报260513.md`

## Gaps

- Older design docs mention five domains and need to be read with the current station domain addition in mind.
- KB context flags exist in the design shape, but expert-specific KB injection policy is not yet fully documented as a product rule.
- Entity resolution remains partly per-domain rather than a shared pipeline.
