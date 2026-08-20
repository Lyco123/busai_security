# Evaluation and Regression

## Test Surfaces

The system uses a mix of automated scripts, fixtures, manual Playwright records, probe pages, and weekly reports.

Automated scripts in `agent/package.json`:

```bash
npm run test:assistant-ab-playwright
npm run test:assistant-reliability-playwright
npm run test:report-output-format-contract
npm run test:rule-config-regression
npm run test:rule-config-edit-regression
npm run check:text
```

Additional scripts:

- `agent/scripts/recall-test-runner.mjs`
- `agent/scripts/vehicle-recall-test.mjs`
- `agent/scripts/plate-tolerance-test.mjs`
- `agent/scripts/assistant-ab-playwright.mjs`
- `agent/scripts/assistant-reliability-playwright.mjs`

## Fixtures

Important fixture files:

- `agent/fixtures/assistant-ab-playwright-cases.json`
- `agent/fixtures/assistant-reliability-cases.json`
- `agent/fixtures/route-report-recall-cases-20260421.json`
- `agent/fixtures/vehicle-report-recall-cases-20260421.json`
- `agent/fixtures/vehicle-plate-tolerance-cases-20260421.json`

## Manual Regression Records

Manual records live in:

- `agent/docs/manual/**`

They cover report routing, recall routing, vehicle plate tolerance, MCP answer quality, and reruns across dates.

## Evaluation Topics

Core areas to evaluate:

- router classification accuracy
- report versus consultation boundary
- multi-turn clarification recovery
- latest report follow-up handling
- rule high-score match behavior
- KB answer quality and citation usefulness
- streaming latency and chunk shape
- MCP tool description quality
- structured report output contract

## Historical Sources

- `agent/docs/Agent测试迭代方案.md`
- `agent/docs/legacy/Agent测试迭代方案-router-skill-ab.md`
- `agent/docs/omni-router-eval-findings-20260316.md`
- `agent/docs/expert-runtime-service-evaluation-20260418.md`
- `agent/docs/manual/**`

## Gaps

- There is no single dashboard for pass/fail trend across all regression surfaces.
- Manual markdown records are not indexed by scenario tags.
- Fixture coverage for KB-specific expert answers should be expanded.
