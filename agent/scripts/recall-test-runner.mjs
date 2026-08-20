import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { request } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const agentRoot = path.resolve(__dirname, '..');
const apiBaseUrl = process.env.ASSISTANT_API_BASE_URL || 'https://api.buso.canocache.com/api/agent';
const fixturesDir = path.join(agentRoot, 'fixtures');
const outputBaseDir = path.join(agentRoot, 'test-results');

const suiteConfigs = [
  {
    name: 'route-report-recall',
    fixtureFile: 'route-report-recall-cases-20260421.json',
    outputDir: path.join(outputBaseDir, 'route-report-recall'),
  },
  {
    name: 'vehicle-report-recall',
    fixtureFile: 'vehicle-report-recall-cases-20260421.json',
    outputDir: path.join(outputBaseDir, 'vehicle-report-recall'),
  },
];

function nowStamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function normalizeContent(value) {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) return value.map(normalizeContent).join(' ').trim();
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value ?? '').trim();
}

function excerpt(value, length = 300) {
  const text = normalizeContent(value).replace(/\s+/g, ' ').trim();
  return text.length > length ? `${text.slice(0, length - 3)}...` : text;
}

function includesAny(text, fragments) {
  return fragments.some((f) => text.includes(f));
}

function inferAskForMoreInfo(text) {
  if (!text) return false;
  return (
    /(请提供|请补充|请确认|请告知|提供更多信息|完整车牌号|车辆ID|线路名称|线路编号|更准确)/.test(
      text
    ) || /没有找到/.test(text)
  );
}

function inferNotFound(text) {
  return /没有找到|未找到/.test(text);
}

function inferReportJson(text) {
  const trimmed = text.trim();
  if (!trimmed.startsWith('{')) return false;
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === 'object' && typeof parsed.report_type === 'string';
  } catch {
    return false;
  }
}

function inferRawToolLeak(text) {
  return /\{\s*"name"\s*:\s*"generate_/.test(text) || /"arguments"\s*:\s*\{/.test(text);
}

function actualToolFromMessage(message) {
  return message?.metadata?.tool || message?.metadata?.ab_test?.selected_tool || null;
}

async function apiJson(api, method, relativePath, data, timeoutMs) {
  const started = performance.now();
  const response = await api.fetch(`${apiBaseUrl}${relativePath}`, {
    method,
    data,
    timeout: timeoutMs,
  });
  const durationMs = Math.round(performance.now() - started);
  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = text;
  }
  return { status: response.status(), payload, durationMs };
}

function evaluateTurnExpectation(turnResult, expect = {}) {
  const failures = [];
  const actualTool = turnResult.tool;

  if (Array.isArray(expect.tool_in) && !expect.tool_in.includes(actualTool)) {
    failures.push(`tool_not_in_allowed:${actualTool ?? 'null'}`);
  }
  if (Array.isArray(expect.tool_not_in) && expect.tool_not_in.includes(actualTool)) {
    failures.push(`tool_forbidden:${actualTool ?? 'null'}`);
  }
  if (
    typeof expect.ask_for_more_info === 'boolean' &&
    turnResult.asks_for_more_info !== expect.ask_for_more_info
  ) {
    failures.push(
      expect.ask_for_more_info ? 'expected_ask_for_more_info' : 'unexpected_ask_for_more_info'
    );
  }
  if (
    Array.isArray(expect.must_contain_any) &&
    !includesAny(turnResult.content, expect.must_contain_any)
  ) {
    failures.push('missing_expected_content');
  }
  if (
    Array.isArray(expect.must_not_contain_any) &&
    includesAny(turnResult.content, expect.must_not_contain_any)
  ) {
    failures.push('contains_forbidden_content');
  }
  if (turnResult.has_raw_tool_leak) {
    failures.push('raw_tool_leak');
  }
  if (turnResult.content_length === 0) {
    failures.push('empty_response');
  }
  return failures;
}

async function runCase(api, testCase) {
  const created = await apiJson(
    api,
    'POST',
    '/sessions',
    { title: `[recall-${testCase.id}]` },
    30000
  );
  const session = created.payload?.data || created.payload;
  const sessionId = session?.id;
  if (!sessionId) {
    throw new Error(`create_session_missing_id:${testCase.id}`);
  }

  const turns = [];
  let cleanup = { deleted: false, error: null };

  try {
    for (const [index, turn] of testCase.turns.entries()) {
      try {
        console.log(
          `  [${testCase.id}] Sending turn ${index + 1}: "${turn.prompt.slice(0, 60)}..."`
        );
        const chat = await apiJson(
          api,
          'POST',
          '/chat',
          { sessionId, content: turn.prompt, messages: [] },
          turn.timeout_ms || 120000
        );
        const message = chat.payload?.data || chat.payload;
        const content = normalizeContent(message?.content);
        const turnResult = {
          index: index + 1,
          prompt: turn.prompt,
          duration_ms: chat.durationMs,
          status: chat.status,
          tool: actualToolFromMessage(message),
          content,
          content_excerpt: excerpt(content),
          content_length: content.length,
          asks_for_more_info: inferAskForMoreInfo(content),
          is_not_found: inferNotFound(content),
          has_report_json: inferReportJson(content),
          has_raw_tool_leak: inferRawToolLeak(content),
        };
        turnResult.failures = evaluateTurnExpectation(turnResult, turn.expect);
        turns.push(turnResult);
        console.log(
          `  [${testCase.id}] Turn ${index + 1} done: tool=${turnResult.tool ?? 'null'} failures=${turnResult.failures.join(',') || 'none'}`
        );
      } catch (error) {
        turns.push({
          index: index + 1,
          prompt: turn.prompt,
          duration_ms: null,
          status: 'error',
          tool: null,
          content: '',
          content_excerpt: '',
          content_length: 0,
          asks_for_more_info: false,
          is_not_found: false,
          has_report_json: false,
          has_raw_tool_leak: false,
          failures: [`request_error:${error.message || String(error)}`],
        });
        console.log(`  [${testCase.id}] Turn ${index + 1} ERROR: ${error.message}`);
        break;
      }
    }
  } finally {
    try {
      await apiJson(api, 'DELETE', `/sessions/${encodeURIComponent(sessionId)}`, undefined, 30000);
      cleanup = { deleted: true, error: null };
    } catch (error) {
      cleanup = { deleted: false, error: error.message || String(error) };
    }
  }

  const failures = turns.flatMap((t) => t.failures.map((f) => `turn${t.index}:${f}`));
  return {
    id: testCase.id,
    category: testCase.category,
    title: testCase.title,
    session_id: sessionId,
    ok: failures.length === 0,
    failure_count: failures.length,
    failures,
    turns,
    cleanup,
  };
}

function renderMarkdown(suiteName, results) {
  const lines = [];
  lines.push(`# ${suiteName} Recall Playwright Report`);
  lines.push('');
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`API Base URL: ${apiBaseUrl}`);
  lines.push('');

  const shouldRecall = results.filter((r) => r.category === 'should_recall');
  const shouldNotRecall = results.filter((r) => r.category === 'should_not_recall');
  const shouldRecallPassed = shouldRecall.filter((r) => r.ok).length;
  const shouldNotRecallPassed = shouldNotRecall.filter((r) => r.ok).length;

  lines.push(`## Summary`);
  lines.push('');
  lines.push(`- Should recall: **${shouldRecallPassed} / ${shouldRecall.length}**`);
  lines.push(`- Should not recall: **${shouldNotRecallPassed} / ${shouldNotRecall.length}**`);
  lines.push('');

  lines.push('## Results Table');
  lines.push('');
  lines.push('| ID | Category | Title | Result | Tool | Failures | Excerpt |');
  lines.push('|---|---|---|---|---|---|---|');
  for (const item of results) {
    const finalTurn = item.turns[item.turns.length - 1] || null;
    lines.push(
      `| ${item.id} | ${item.category} | ${item.title} | ${item.ok ? 'PASS' : 'FAIL'} | ${finalTurn?.tool ?? 'null'} | ${item.failures.join(', ') || '-'} | ${finalTurn?.content_excerpt ?? '-'} |`
    );
  }
  lines.push('');

  lines.push('## Turn Details');
  lines.push('');
  for (const item of results) {
    lines.push(`### ${item.id} — ${item.title}`);
    lines.push(`- category: ${item.category}`);
    lines.push(`- result: ${item.ok ? 'PASS' : 'FAIL'}`);
    lines.push(`- failures: ${item.failures.join(', ') || '-'}`);
    for (const turn of item.turns) {
      lines.push(
        `- turn ${turn.index}: tool=${turn.tool ?? 'null'} duration_ms=${turn.duration_ms ?? '-'} failures=${turn.failures.join(', ') || '-'}`
      );
      lines.push(`  prompt: ${turn.prompt}`);
      lines.push(`  excerpt: ${turn.content_excerpt || '-'}`);
    }
    lines.push('');
  }
  return `${lines.join('\n')}\n`;
}

async function runSuite(suiteConfig) {
  const fixturePath = path.join(fixturesDir, suiteConfig.fixtureFile);
  const raw = await fs.readFile(fixturePath, 'utf8');
  const cases = JSON.parse(raw);

  await fs.mkdir(suiteConfig.outputDir, { recursive: true });

  console.log(`\n=== Running suite: ${suiteConfig.name} (${cases.length} cases) ===`);

  const api = await request.newContext();
  const results = [];

  try {
    for (const testCase of cases) {
      console.log(`[${suiteConfig.name}] Running case: ${testCase.id}`);
      const result = await runCase(api, testCase);
      results.push(result);
      console.log(
        `[${suiteConfig.name}] Case ${testCase.id}: ${result.ok ? 'PASS' : 'FAIL'} (${result.failure_count} failures)`
      );
    }
  } finally {
    await api.dispose();
  }

  const run = {
    generated_at: new Date().toISOString(),
    suite_name: suiteConfig.name,
    total_cases: results.length,
    passed_cases: results.filter((r) => r.ok).length,
    failed_cases: results.filter((r) => !r.ok).length,
    results,
  };

  const stamp = nowStamp();
  const jsonPath = path.join(suiteConfig.outputDir, `${stamp}.json`);
  const mdPath = path.join(suiteConfig.outputDir, `${stamp}.md`);
  const latestJsonPath = path.join(suiteConfig.outputDir, 'latest.json');
  const latestMdPath = path.join(suiteConfig.outputDir, 'latest.md');

  const jsonText = JSON.stringify(run, null, 2);
  const markdown = renderMarkdown(suiteConfig.name, results);

  await fs.writeFile(jsonPath, jsonText);
  await fs.writeFile(mdPath, markdown);
  await fs.writeFile(latestJsonPath, jsonText);
  await fs.writeFile(latestMdPath, markdown);

  console.log(`\n=== Suite ${suiteConfig.name} complete ===`);
  console.log(`  Passed: ${run.passed_cases}/${run.total_cases}`);
  console.log(`  Output: ${mdPath}`);
  console.log(`  Latest: ${latestMdPath}`);

  return run;
}

async function main() {
  const allResults = {};
  for (const suiteConfig of suiteConfigs) {
    allResults[suiteConfig.name] = await runSuite(suiteConfig);
  }

  console.log('\n=== All suites complete ===');
  for (const [name, run] of Object.entries(allResults)) {
    const shouldRecall = run.results.filter((r) => r.category === 'should_recall');
    const shouldNotRecall = run.results.filter((r) => r.category === 'should_not_recall');
    console.log(
      `  ${name}: should_recall=${shouldRecall.filter((r) => r.ok).length}/${shouldRecall.length} should_not_recall=${shouldNotRecall.filter((r) => r.ok).length}/${shouldNotRecall.length}`
    );
  }
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exitCode = 1;
});
