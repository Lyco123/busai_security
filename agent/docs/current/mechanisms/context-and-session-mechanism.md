# Context and Session Mechanism

## Purpose

Session context lets the agent handle multi-turn tasks: report follow-ups, missing parameter recovery, clarification, and recent answer continuation.

## Main Context Sources

- Chat history from session messages.
- Latest assistant routing context.
- Latest structured report source.
- Latest structured report failure source.
- Pending clarification state.
- Server time context.
- Rule match and work scenario context.
- Expert runtime context.

Primary files:

- `agent/src/domains/chat/chat-service.ts`
- `agent/src/domains/chat/context.ts`
- `agent/src/domains/chat/turn-context.ts`
- `agent/src/domains/chat/clarification-state.ts`
- `agent/src/domains/sessions/repository.ts`
- `agent/src/domains/sessions/routing-context.ts`
- `agent/src/domains/experts/context-builder.ts`
- `agent/src/domains/chat/server-time-context.ts`

## Pending Clarification

Pending clarification is used when a selected tool needs missing parameters. The next user turn can resume the previous task if it appears to provide the missing slots.

Important distinction:

- Short answer that completes missing data: resume old task.
- New business question: route as new task.
- Correction to existing report parameters: regenerate or update as appropriate.

## Latest Report Context

Latest report context supports:

- explaining the previous report
- answering follow-up questions
- regenerating with changed parameters
- recovering from report generation failure

The context should not force every subsequent question back into the report path.

## Session Persistence

The system stores messages and session metadata in D1 through session repositories. Assistant messages can carry:

- content
- status
- metadata
- sources
- routing information

## Historical Sources

- `agent/docs/session-context-0129.md`
- `agent/docs/assistant-session-concurrency-devdoc-20260428.md`
- `agent/docs/router-prompt-followups-20260416.md`

## Gaps

- There is no single state-machine document for all multi-turn states. Rule config has a more explicit state-machine direction, but global chat state is still distributed.
- Slot filling behavior is partly prompt-driven and partly validation-driven.
