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
const outputDir = path.join(agentRoot, 'test-results', 'vehicle-report-recall');
const fixtureFile = 'vehicle-report-recall-cases-20260421.json';

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
    /(请提供|请补充|请确认|请告知|提供更多信息|完整车牌号|车辆ID|线路名称|更准确)/.test(text) ||
    /没有找到/.test(text)
  );
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
  if (Array.isArray(expect.tool_in) && !expect.tool_in.includes(actualTool))
    failures.push(`tool_not_in_allowed:${actualTool ?? 'null'}`);
  if (Array.isArray(expect.tool_not_in) && expect.tool_not_in.includes(actualTool))
    failures.push(`tool_forbidden:${actualTool ?? 'null'}`);
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
  )
    failures.push('missing_expected_content');
  if (
    Array.isArray(expect.must_not_contain_any) &&
    includesAny(turnResult.content, expect.must_not_contain_any)
  )
    failures.push('contains_forbidden_content');
  if (turnResult.has_raw_tool_leak) failures.push('raw_tool_leak');
  if (turnResult.content_length === 0) failures.push('empty_response');
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
  if (!sessionId) throw new Error(`create_session_missing_id:${testCase.id}`);
  const turns = [];
  let cleanup = { deleted: false, error: null };
  try {
    for (const [index, turn] of testCase.turns.entries()) {
      try {
        console.log(`  [${testCase.id}] Sending turn ${index + 1}`);
        const chat = await apiJson(
          api,
          'POST',
          '/chat',
          { sessionId, content: turn.prompt, messages: [] },
          turn.timeout_ms || 180000
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
          has_raw_tool_leak: false,
          failures: [`request_error:${error.message}`],
        });
        break;
      }
    }
  } finally {
    try {
      await apiJson(api, 'DELETE', `/sessions/${encodeURIComponent(sessionId)}`, undefined, 30000);
      cleanup = { deleted: true, error: null };
    } catch (e) {
      cleanup = { deleted: false, error: e.message };
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

function renderMarkdown(results) {
  const lines = [];
  lines.push('# vehicle-report-recall Recall Playwright Report');
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`API Base URL: ${apiBaseUrl}`);
  const shouldRecall = results.filter((r) => r.category === 'should_recall');
  const shouldNotRecall = results.filter((r) => r.category === 'should_not_recall');
  lines.push(
    `- Should recall: **${shouldRecall.filter((r) => r.ok).length} / ${shouldRecall.length}**`
  );
  lines.push(
    `- Should not recall: **${shouldNotRecall.filter((r) => r.ok).length} / ${shouldNotRecall.length}**`
  );
  lines.push('| ID | Category | Title | Result | Tool | Failures | Excerpt |');
  lines.push('|---|---|---|---|---|---|---|');
  for (const item of results) {
    const finalTurn = item.turns[item.turns.length - 1] || null;
    lines.push(
      `| ${item.id} | ${item.category} | ${item.title} | ${item.ok ? 'PASS' : 'FAIL'} | ${finalTurn?.tool ?? 'null'} | ${item.failures.join(', ') || '-'} | ${finalTurn?.content_excerpt ?? '-'} |`
    );
  }
  for (const item of results) {
    lines.push(`### ${item.id} — ${item.title}`);
    lines.push(`- result: ${item.ok ? 'PASS' : 'FAIL'}`);
    for (const turn of item.turns) {
      lines.push(
        `- turn ${turn.index}: tool=${turn.tool ?? 'null'} duration_ms=${turn.duration_ms ?? '-'} failures=${turn.failures.join(', ') || '-'}`
      );
      lines.push(`  excerpt: ${turn.content_excerpt || '-'}`);
    }
  }
  return `${lines.join('\n')}\n`;
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const raw = await fs.readFile(path.join(fixturesDir, fixtureFile), 'utf8');
  const cases = JSON.parse(raw);
  console.log(`Running vehicle-report-recall: ${cases.length} cases`);
  const api = await request.newContext();
  const results = [];
  try {
    for (const testCase of cases) {
      console.log(`Running case: ${testCase.id}`);
      results.push(await runCase(api, testCase));
    }
  } finally {
    await api.dispose();
  }
  const stamp = nowStamp();
  const jsonText = JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2);
  const markdown = renderMarkdown(results);
  await fs.writeFile(path.join(outputDir, `${stamp}.json`), jsonText);
  await fs.writeFile(path.join(outputDir, `${stamp}.md`), markdown);
  await fs.writeFile(path.join(outputDir, 'latest.json'), jsonText);
  await fs.writeFile(path.join(outputDir, 'latest.md'), markdown);
  const shouldRecall = results.filter((r) => r.category === 'should_recall');
  const shouldNotRecall = results.filter((r) => r.category === 'should_not_recall');
  console.log(`\nShould recall: ${shouldRecall.filter((r) => r.ok).length}/${shouldRecall.length}`);
  console.log(
    `Should not recall: ${shouldNotRecall.filter((r) => r.ok).length}/${shouldNotRecall.length}`
  );
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
