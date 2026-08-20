# Router Optimization 2026-05-18

## Scope

This change optimizes the existing heavy router only. It does not add a lightweight router, router-specific timeout, dedicated router model, history truncation, or forced dispatch.

## Changes

1. Shared query embedding
   - `executeMatchRules` can now expose the query embedding through an internal callback.
   - `routeRequest` passes that embedding into work-scenario matching.
   - This removes the duplicated rule/scenario query embedding call when rule matching has already produced an embedding.

2. Compact router prompt
   - `agent/skills/router/SKILL.md` was rewritten from repeated per-domain rules into a compact decision policy.
   - The retained policy covers rule priority, multi-turn carry-over, report vs consultation boundaries, domain expert routing, `cot_mode`, and clarification behavior.

3. Compact router tool schema
   - `agent/src/domains/chat/router-tools.ts` now uses shorter tool descriptions.
   - The most important boundaries remain: report tools are only for explicit report products; consultation/query/report-follow-up goes to consult tools; fleet-level metadata/list/statistics goes to `consult_omni`.

4. Router allow-list contract
   - `buildRouterTools(undefined)` means all router tools.
   - `buildRouterTools([])` means no tools.
   - This fixes the previous ambiguity where an empty list accidentally behaved like all tools.
   - Router chat-completion requests omit `tools` and `tool_choice` when the final tool list is empty.

5. Probe-only command router experiment
   - Pipeline stream probe can now set `useCommandRouter` on `routeRequest`.
   - This path asks the model for a compact JSON command instead of OpenAI-compatible `tools` / function-calling output.
   - Production chat streams do not set this option.
   - If the command output is invalid or selects a non-allowed tool, the probe falls back to the existing function-calling router.
   - Probe stages include `command_router_call_started`, `command_router_call_done`, and `command_router_fallback_to_function_router`.

## Risk Notes

The prompt and tool schema compression can affect routing recall and precision. If regressions appear, inspect these files first:

- `agent/skills/router/SKILL.md`
- `agent/src/domains/chat/router-tools.ts`

Likely regression areas:

- Report generation vs consultation boundary.
- Vehicle expert vs `consult_omni` for fleet-level vehicle metadata.
- Rule-hit handling, especially near-threshold matches.
- Multi-turn continuation after clarification or report follow-up.
- `cot_mode` selection for domain experts.
- Probe command router JSON parsing and fallback rate.

## Rollback / Diagnosis

If routing quality drops:

1. Compare the changed prompt and tool descriptions against the previous version.
2. Use the stream probe pipeline mode to check `rule_match_done`, `router_call_done`, selected tool, and worker start timing.
3. Re-expand only the affected domain block instead of restoring all repeated text.
4. Keep the allow-list contract unless a caller explicitly depends on the old ambiguous behavior.
5. For command router issues, compare `command_router_call_done.preview`, `router_call_done.router_mode`, and selected tool against the function-calling router result.

## Not Changed

- Router timeout remains governed by existing OpenAI request timeout behavior.
- Router model selection still uses `OPENAI_ROUTER_MODEL || OPENAI_MODEL || DEFAULT_MODEL`.
- Router history context size is unchanged.
- Router is not forced to produce a tool call.
- Production streaming protocol is unchanged.
- Production routing still uses the existing function-calling router unless a caller explicitly sets `useCommandRouter`.
