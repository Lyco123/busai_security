import fs from 'node:fs/promises';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { request } from 'playwright';

const __dirname = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1'));
const agentRoot = path.resolve(__dirname, '..');
const apiBaseUrl = 'https://api.buso.canocache.com/api/agent';
const fixturesDir = path.join(agentRoot, 'fixtures');
const outputDir = path.join(agentRoot, 'test-results', 'vehicle-plate-tolerance');
const fixtureFile = 'vehicle-plate-tolerance-cases-20260421.json';

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
    /(请提供|请补充|请确认|请告知|提供更多信息|完整车牌号|车辆ID|更准确)/.test(text) ||
    /没有找到/.test(text)
  );
}

function inferNotFound(text) {
  return /没有找到|未找到/.test(text);
}

function inferRawToolLeak(text) {
  return /\{\s*"name"\s*:\s*"generate_/.test(text) || /"arguments"\s*:\s*\{/.test(text);
}

function actualToolFromMessage(message) {
  return message?.metadata?.tool || message?.metadata?.ab_test?.selected_tool || null;
}

async function apiJson(api, method, relativePath, data, timeoutMs, retries = 3) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
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
    } catch (error) {
      if (attempt < retries) {
        console.log(
          `  Retry ${attempt}/${retries} for ${method} ${relativePath}: ${error.message}`
        );
        await new Promise((r) => setTimeout(r, 5000));
      } else {
        throw error;
      }
    }
  }
  throw new Error('unreachable');
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
    { title: `[plate-tol-${testCase.id}]` },
    30000
  );
  const session = created.payload?.data || created.payload;
  const sessionId = session?.id;
  if (!sessionId) throw new Error(`create_session_missing_id:${testCase.id}`);
  const turns = [];
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
          is_not_found: inferNotFound(content),
          has_raw_tool_leak: inferRawToolLeak(content),
        };
        turnResult.failures = evaluateTurnExpectation(turnResult, turn.expect);
        turns.push(turnResult);
        console.log(
          `  [${testCase.id}] Turn ${index + 1} done: tool=${turnResult.tool ?? 'null'} ask_more=${turnResult.asks_for_more_info} not_found=${turnResult.is_not_found} failures=${turnResult.failures.join(',') || 'none'}`
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
          has_raw_tool_leak: false,
          failures: [`request_error:${error.message}`],
        });
        break;
      }
    }
  } finally {
    try {
      await apiJson(api, 'DELETE', `/sessions/${encodeURIComponent(sessionId)}`, undefined, 30000);
    } catch {}
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
  };
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const raw = await fs.readFile(path.join(fixturesDir, fixtureFile), 'utf8');
  const cases = JSON.parse(raw);
  console.log(`Running vehicle-plate-tolerance: ${cases.length} cases`);
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

  const routingSuccess = results.filter((r) => {
    const finalTurn = r.turns[r.turns.length - 1];
    return finalTurn?.tool === 'generate_vehicle_report';
  }).length;
  const dataHit = results.filter((r) => !r.turns.some((t) => t.is_not_found)).length;

  console.log(`\nRouting tolerance success: ${routingSuccess}/${results.length}`);
  console.log(`Data hit (粤A plates): ${dataHit}/${results.length}`);

  const jsonText = JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      routing_success: routingSuccess,
      total: results.length,
      results,
    },
    null,
    2
  );
  const lines = [];
  lines.push('# Vehicle Plate Tolerance Test Report');
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`Routing tolerance success: **${routingSuccess} / ${results.length}**`);
  lines.push(`Data hit: **${dataHit} / ${results.length}**`);
  lines.push('');
  lines.push('| ID | Type | Tool | Route OK | Data Found | Excerpt |');
  lines.push('|---|---|---|---|---|---|');
  for (const item of results) {
    const finalTurn = item.turns[item.turns.length - 1];
    const routeOk = finalTurn?.tool === 'generate_vehicle_report' ? 'YES' : 'NO';
    const dataFound = item.turns.some((t) => t.is_not_found) ? 'NO' : 'YES';
    lines.push(
      `| ${item.id} | ${item.title} | ${finalTurn?.tool ?? 'null'} | ${routeOk} | ${dataFound} | ${finalTurn?.content_excerpt ?? '-'} |`
    );
  }
  const markdown = `${lines.join('\n')}\n`;

  await fs.writeFile(path.join(outputDir, 'latest.json'), jsonText);
  await fs.writeFile(path.join(outputDir, 'latest.md'), markdown);
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
