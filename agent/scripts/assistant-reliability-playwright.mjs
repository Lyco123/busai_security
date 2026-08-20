import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { chromium, request } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const agentRoot = path.resolve(__dirname, '..');
const casesPath = path.join(agentRoot, 'fixtures', 'assistant-reliability-cases.json');
const assistantUrl = process.env.ASSISTANT_URL || 'https://busodemo.canocache.com/assistant';
const apiBaseUrl = process.env.ASSISTANT_API_BASE_URL || 'https://api.buso.canocache.com/api/agent';
const outputDir = path.join(agentRoot, 'test-results', 'assistant-reliability');
const headless = !['0', 'false', 'no'].includes(
  String(process.env.ASSISTANT_HEADLESS || 'true').trim().toLowerCase()
);

function nowStamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function tryParseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function normalizeContent(value) {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) return value.map((item) => normalizeContent(item)).join(' ').trim();
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value ?? '').trim();
}

function excerpt(value, length = 220) {
  const text = normalizeContent(value).replace(/\s+/g, ' ').trim();
  return text.length > length ? `${text.slice(0, length - 3)}...` : text;
}

function includesAny(text, fragments) {
  return fragments.some((fragment) => text.includes(fragment));
}

function inferAskForMoreInfo(text) {
  if (!text) return false;
  return (
    /(请提供|请补充|请确认|请告知|提供更多信息|完整车牌号|车辆ID|线路名称|线路编号|事故编号|更准确)/.test(text) ||
    /没有找到/.test(text)
  );
}

function inferNotFound(text) {
  return /没有找到|未找到/.test(text);
}

function inferReportJson(text) {
  const trimmed = text.trim();
  if (!trimmed.startsWith('{')) return false;
  const parsed = tryParseJson(trimmed);
  if (!parsed || typeof parsed !== 'object') return false;
  return typeof parsed.report_type === 'string';
}

function inferRawToolLeak(text) {
  return /\{\s*"name"\s*:\s*"generate_/.test(text) || /"arguments"\s*:\s*\{/.test(text);
}

function actualToolFromMessage(message) {
  return (
    message?.metadata?.tool ||
    message?.metadata?.ab_test?.selected_tool ||
    null
  );
}

async function ensureOutputDir() {
  await fs.mkdir(outputDir, { recursive: true });
}

async function loadCases() {
  const raw = await fs.readFile(casesPath, 'utf8');
  return JSON.parse(raw);
}

async function runBrowserSmoke() {
  const browser = await chromium.launch({ headless });
  const context = await browser.newContext();
  const page = await context.newPage();
  const result = {
    ok: false,
    url: assistantUrl,
    checks: [],
    error: null,
  };

  try {
    await page.goto(assistantUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.getByRole('textbox', {
      name: '输入消息，回车发送，按住上档键再回车换行',
    }).waitFor({ state: 'visible', timeout: 60000 });
    await page.getByRole('button', { name: '新建对话' }).waitFor({ state: 'visible', timeout: 60000 });
    const sendDisabled = await page.getByRole('button', { name: '发送' }).isDisabled();
    result.checks.push({ name: 'assistant_page_loaded', ok: true });
    result.checks.push({ name: 'input_visible', ok: true });
    result.checks.push({ name: 'new_chat_visible', ok: true });
    result.checks.push({ name: 'send_disabled_when_empty', ok: sendDisabled });
    result.ok = result.checks.every((item) => item.ok);
  } catch (error) {
    result.error = { message: error.message || String(error) };
  } finally {
    await context.close();
    await browser.close();
  }

  return result;
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

  if (expect.response_kind === 'report_json' && !turnResult.has_report_json) {
    failures.push('expected_report_json');
  }
  if (expect.response_kind === 'clarify' && !turnResult.is_clarify) {
    failures.push('expected_clarify');
  }
  if (expect.response_kind === 'text' && turnResult.has_report_json) {
    failures.push('unexpected_report_json');
  }
  if (typeof expect.ask_for_more_info === 'boolean' && turnResult.asks_for_more_info !== expect.ask_for_more_info) {
    failures.push(
      expect.ask_for_more_info ? 'expected_ask_for_more_info' : 'unexpected_ask_for_more_info'
    );
  }
  if (typeof expect.min_length === 'number' && turnResult.content_length < expect.min_length) {
    failures.push(`response_too_short:${turnResult.content_length}`);
  }
  if (Array.isArray(expect.tool_in) && !expect.tool_in.includes(actualTool)) {
    failures.push(`tool_not_allowed:${actualTool}`);
  }
  if (Array.isArray(expect.tool_not_in) && expect.tool_not_in.includes(actualTool)) {
    failures.push(`tool_forbidden:${actualTool}`);
  }
  if (Array.isArray(expect.must_contain_any) && !includesAny(turnResult.content, expect.must_contain_any)) {
    failures.push('missing_expected_content');
  }
  if (Array.isArray(expect.must_not_contain_any) && includesAny(turnResult.content, expect.must_not_contain_any)) {
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
  const created = await apiJson(api, 'POST', '/sessions', { title: `[assistant-reliability] ${testCase.id}` }, 30000);
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
        const chat = await apiJson(
          api,
          'POST',
          '/chat',
          { sessionId, content: turn.prompt, messages: [] },
          turn.timeout_ms || 30000
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
          is_clarify: inferAskForMoreInfo(content),
          has_report_json: inferReportJson(content),
          has_raw_tool_leak: inferRawToolLeak(content),
          metadata: {
            ab_test: message?.metadata?.ab_test || null,
            rule_match: message?.metadata?.rule_match || null,
            scenario: message?.metadata?.scenario || null,
          },
        };
        turnResult.failures = evaluateTurnExpectation(turnResult, turn.expect);
        turns.push(turnResult);
        if (turnResult.failures.length) break;
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
          is_clarify: false,
          has_report_json: false,
          has_raw_tool_leak: false,
          metadata: null,
          failures: [`request_error:${error.message || String(error)}`],
        });
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

  const failures = turns.flatMap((turn) => turn.failures.map((failure) => `turn${turn.index}:${failure}`));
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

function buildSummary(browserSmoke, cases) {
  const passed = cases.filter((item) => item.ok).length;
  const failedCases = cases.filter((item) => !item.ok);
  return {
    browser_smoke_ok: browserSmoke.ok,
    total_cases: cases.length,
    passed_cases: passed,
    failed_cases: failedCases.length,
    failed_case_ids: failedCases.map((item) => item.id),
  };
}

function renderMarkdown(run) {
  const lines = [];
  lines.push('# Assistant Reliability Playwright Report');
  lines.push('');
  lines.push(`- Assistant URL: \`${assistantUrl}\``);
  lines.push(`- API Base URL: \`${apiBaseUrl}\``);
  lines.push(`- Browser smoke: \`${run.browser_smoke.ok}\``);
  lines.push(`- Passed cases: \`${run.summary.passed_cases}/${run.summary.total_cases}\``);
  lines.push(`- Failed cases: \`${run.summary.failed_cases}\``);
  lines.push('');
  lines.push('## Browser Smoke');
  for (const check of run.browser_smoke.checks) {
    lines.push(`- ${check.name}: \`${check.ok}\``);
  }
  if (run.browser_smoke.error) {
    lines.push(`- error: \`${run.browser_smoke.error.message}\``);
  }
  lines.push('');
  lines.push('## Cases');
  lines.push('');
  lines.push('| Case | Category | Result | Failures | Final Tool | Final Excerpt |');
  lines.push('|---|---|---:|---|---|---|');
  for (const item of run.cases) {
    const finalTurn = item.turns[item.turns.length - 1] || null;
    lines.push(
      `| ${item.id} | ${item.category} | ${item.ok ? 'PASS' : 'FAIL'} | ${item.failures.join(', ') || '-'} | ${finalTurn?.tool ?? '-'} | ${finalTurn?.content_excerpt ?? '-'} |`
    );
  }
  lines.push('');
  lines.push('## Turn Details');
  lines.push('');
  for (const item of run.cases) {
    lines.push(`### ${item.id}`);
    lines.push(`- title: ${item.title}`);
    lines.push(`- result: ${item.ok ? 'PASS' : 'FAIL'}`);
    lines.push(`- failures: ${item.failures.join(', ') || '-'}`);
    for (const turn of item.turns) {
      lines.push(
        `- turn ${turn.index}: tool=${turn.tool ?? 'null'} ask_more=${turn.asks_for_more_info} report_json=${turn.has_report_json} duration_ms=${turn.duration_ms ?? '-'} failures=${turn.failures.join(', ') || '-'}`
      );
      lines.push(`  prompt: ${turn.prompt}`);
      lines.push(`  excerpt: ${turn.content_excerpt || '-'}`);
    }
    lines.push('');
  }
  return `${lines.join('\n')}\n`;
}

async function writeOutputs(run) {
  const stamp = nowStamp();
  const jsonPath = path.join(outputDir, `${stamp}.json`);
  const mdPath = path.join(outputDir, `${stamp}.md`);
  const latestJsonPath = path.join(outputDir, 'latest.json');
  const latestMdPath = path.join(outputDir, 'latest.md');
  const jsonText = JSON.stringify(run, null, 2);
  const markdown = renderMarkdown(run);
  await fs.writeFile(jsonPath, jsonText);
  await fs.writeFile(mdPath, markdown);
  await fs.writeFile(latestJsonPath, jsonText);
  await fs.writeFile(latestMdPath, markdown);
  return { jsonPath, mdPath, latestJsonPath, latestMdPath };
}

async function main() {
  await ensureOutputDir();
  const cases = await loadCases();
  const browserSmoke = await runBrowserSmoke();
  const api = await request.newContext();
  const results = [];

  try {
    for (const testCase of cases) {
      results.push(await runCase(api, testCase));
    }
  } finally {
    await api.dispose();
  }

  const run = {
    generated_at: new Date().toISOString(),
    browser_smoke: browserSmoke,
    summary: buildSummary(browserSmoke, results),
    cases: results,
  };
  const outputs = await writeOutputs(run);

  console.log(JSON.stringify({ summary: run.summary, outputs }, null, 2));

  if (!browserSmoke.ok || run.summary.failed_cases > 0) {
    process.exitCode = 1;
  }
}

main().catch(async (error) => {
  await ensureOutputDir();
  const failureRun = {
    generated_at: new Date().toISOString(),
    fatal_error: error.message || String(error),
  };
  const stamp = nowStamp();
  const jsonPath = path.join(outputDir, `${stamp}-fatal.json`);
  await fs.writeFile(jsonPath, JSON.stringify(failureRun, null, 2));
  console.error(error);
  process.exitCode = 1;
});
