# Test Case Index

## Automated Scripts

From `agent/package.json`:

- `test:assistant-ab-playwright`
- `test:assistant-reliability-playwright`
- `test:report-output-format-contract`
- `test:rule-config-regression`
- `test:rule-config-edit-regression`
- `check:text`

Additional scripts under `agent/scripts/`:

- `assistant-ab-playwright.mjs`
- `assistant-reliability-playwright.mjs`
- `browser-engine.mjs`
- `plate-tolerance-test.mjs`
- `recall-test-runner.mjs`
- `report-output-format-contract.mjs`
- `reset-ab-test-stats.mjs`
- `rule-config-edit-regression.mjs`
- `rule-config-regression.mjs`
- `vehicle-recall-test.mjs`

## Fixture Groups

- Assistant AB/reliability: `agent/fixtures/assistant-*.json`
- Vehicle recall and tolerance: `agent/fixtures/vehicle-*.json`
- Route report recall: `agent/fixtures/route-*.json`

## Manual Groups

Manual regression docs are in `agent/docs/manual/`.

High-value groups:

- `vehicle-report-*`
- `driver-report-*`
- `route-report-*`
- `unit-report-*`
- `accident-report-*`
- `mcp-new-stats-*`
- `report-routing-*`

## Retrieval Tests

Retrieval service tests:

- `agent/retrieval/tests/*.test.ts`
- `agent/retrieval/ocr-service/tests/*.py`

Retrieval latest check:

- `agent/retrieval-latest-check/tests/*.test.ts`

## Gaps

- Manual docs are not indexed by expected tool, domain, and pass/fail status.
- No single command runs all Worker plus retrieval plus OCR checks.
- Test data ownership and refresh cadence need a separate policy.
