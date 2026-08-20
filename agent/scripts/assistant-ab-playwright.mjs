import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const agentRoot = path.resolve(__dirname, '..');
const casesPath = path.join(agentRoot, 'fixtures', 'assistant-ab-playwright-cases.json');
const defaultAssistantUrl = 'https://busodemo.canocache.com/assistant';
const defaultApiBaseUrl = 'https://api.buso.canocache.com/api/agent';
const defaultOutputDir = path.join(agentRoot, 'test-results', 'assistant-ab');
const statsProbePrompt = '巴士集团车辆类型有哪些';

function envBoolean(value, fallback) {
  if (value === undefined) return fallback;
  const normalized = String(value).trim().toLowerCase();
  if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) return false;
  return fallback;
}

function envNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function nowStamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function joinUrl(baseUrl, relativePath) {
  return `${String(baseUrl).replace(/\/+$/, '')}/${String(relativePath).replace(/^\/+/, '')}`;
}

function tryParseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function unwrapData(payload) {
  if (payload && typeof payload === 'object' && 'data' in payload && payload.data !== undefined) {
    return payload.data;
  }
  return payload;
}

function normalizeContent(value) {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) return value.map((item) => normalizeContent(item)).join(' ').trim();
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value ?? '').trim();
}

function excerpt(value, length = 140) {
  const text = normalizeContent(value).replace(/\s+/g, ' ').trim();
  return text.length > length ? `${text.slice(0, length - 3)}...` : text;
}

function extractApiBaseUrl(url) {
  const match = String(url).match(/^(https?:\/\/[^?#]+\/api\/agent)(?:\/|$)/i);
  return match ? match[1] : null;
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function percentile(values, ratio) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * ratio) - 1));
  return sorted[index];
}

function roundNumber(value) {
  return Number.isFinite(value) ? Math.round(value) : null;
}

function mean(values) {
  if (!values.length) return null;
  return roundNumber(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function includesAny(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

function inferAskForMoreInfo(text) {
  const normalized = normalizeContent(text);
  if (!normalized) return false;
  return includesAny(normalized, [
    /请提供/,
    /请告知/,
    /需要(?:您|你)?提供/,
    /还需要.*信息/,
    /请补充/,
    /未找到.*请提供/,
    /更准确的车牌号/,
    /车辆ID/,
    /profile ID/,
  ]);
}

function safeError(error) {
  if (!error) return { message: 'unknown_error' };
  return {
    message: error.message || String(error),
    status: error.status || null,
    code: error.code || null,
    payload: error.payload || null,
  };
}

class AssistantApi {
  constructor(requestContext, baseUrl, timeoutMs) {
    this.requestContext = requestContext;
    this.baseUrl = baseUrl;
    this.timeoutMs = timeoutMs;
  }

  async json(method, relativePath, data) {
    const started = performance.now();
    let response;
    try {
      response = await this.requestContext.fetch(joinUrl(this.baseUrl, relativePath), {
        method,
        data,
        timeout: this.timeoutMs,
      });
    } catch (error) {
      const wrapped = new Error(`network_error ${method} ${relativePath}: ${error.message}`);
      wrapped.code = 'network_error';
      throw wrapped;
    }

    const durationMs = roundNumber(performance.now() - started);
    const rawText = await response.text();
    const payload = tryParseJson(rawText);

    if (!response.ok) {
      const error = new Error(`http_${response.status} ${method} ${relativePath}`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }

    return {
      status: response.status,
      durationMs,
      payload,
      data: unwrapData(payload),
    };
  }

  authMe() {
    return this.json('GET', '/auth/me');
  }

  createSession(title) {
    return this.json('POST', '/sessions', { title });
  }

  chat(sessionId, content, abGroup) {
    // Current production experiment is server-assigned by session; abGroup is only
    // forwarded for compatibility with older/local override flows.
    return this.json('POST', '/chat', {
      sessionId,
      content,
      messages: [],
      abGroup,
    });
  }

  deleteSession(sessionId) {
    return this.json('DELETE', `/sessions/${encodeURIComponent(sessionId)}`);
  }

  getStats() {
    return this.json('GET', '/ab-test/stats');
  }
}

async function loadCases(config) {
  const raw = await fs.readFile(casesPath, 'utf8');
  const cases = JSON.parse(raw);
  let filtered = Array.isArray(cases) ? cases : [];

  if (config.caseFilter) {
    filtered = filtered.filter((testCase) => {
      const haystack = `${testCase.id} ${testCase.title} ${testCase.scenario_type}`.toLowerCase();
      return haystack.includes(config.caseFilter.toLowerCase());
    });
  }

  if (config.caseLimit) {
    filtered = filtered.slice(0, config.caseLimit);
  }

  return filtered;
}

async function ensureOutputDir(outputDir) {
  await fs.mkdir(outputDir, { recursive: true });
}

async function loginToAssistant(page, config) {
  const apiBases = new Set();
  page.on('request', (request) => {
    const base = extractApiBaseUrl(request.url());
    if (base) apiBases.add(base);
  });

  await page.goto(config.assistantUrl, { waitUntil: 'domcontentloaded', timeout: config.timeoutMs });

  const logoutVisible = await page.getByRole('button', { name: '退出登录' }).isVisible().catch(() => false);
  if (!logoutVisible) {
    const loginVisible = await page.getByRole('button', { name: '登录' }).isVisible().catch(() => false);
    if (loginVisible) {
      if (!config.username || !config.password) {
        throw new Error('missing ASSISTANT_USERNAME or ASSISTANT_PASSWORD');
      }

      await page.getByRole('button', { name: '登录' }).click();
      await page.waitForURL(/\/login(?:$|\?)/, { timeout: config.timeoutMs });
      await page.getByPlaceholder('请输入用户名').fill(config.username);
      await page.locator('input[placeholder="请输入密码"]').fill(config.password);
      await page.getByRole('button', { name: '登录' }).click();
      await page.waitForURL(/\/assistant(?:$|\?)/, { timeout: config.timeoutMs });
    }
  }

  await page.getByText('车辆专家 CoT 开关实验').waitFor({ state: 'visible', timeout: config.timeoutMs });
  const statsVisible = await page.getByText('A/B 统计').isVisible().catch(() => false);
  const apiBaseUrl = config.apiBaseUrl || [...apiBases][0] || defaultApiBaseUrl;

  return { apiBaseUrl, statsVisible };
}

function simplifyStats(stats) {
  if (!stats) return null;
  const metricMap = Object.fromEntries((stats.metrics || []).map((item) => [item.key, item.values]));
  return {
    experiment: stats.experiment,
    sample_turns: stats.sample_turns,
    sample_sessions: stats.sample_sessions,
    turns: metricMap.turns || null,
    omni_selected: metricMap.omni_selected || null,
    vehicle_expert_selected: metricMap.vehicle_expert_selected || null,
    rule_reply_selected: metricMap.rule_reply_selected || null,
    report_selected: metricMap.report_selected || null,
    other_selected: metricMap.other_selected || null,
    updated_at: stats.updated_at || null,
  };
}

function summarizeTurn(testCase, group, prompt, chatResult) {
  const message = unwrapData(chatResult.data);
  const content = normalizeContent(message?.content);
  const abTest = message?.metadata?.ab_test || {};

  return {
    prompt,
    group,
    duration_ms: chatResult.durationMs,
    message_id: message?.id || null,
    content_excerpt: excerpt(content),
    content_length: content.length,
    asks_for_more_info: inferAskForMoreInfo(content),
    empty_response: content.length === 0,
    tool: abTest.selected_tool || message?.metadata?.tool || null,
    ab_test: {
      experiment: abTest.experiment || null,
      group: abTest.group || null,
      source: abTest.source || null,
      routing_mode: abTest.routing_mode || null,
      selected_tool: abTest.selected_tool || null,
      locked: abTest.locked ?? null,
    },
    should_ask_for_info: testCase.should_ask_for_info,
  };
}

function aggregateGroupResult(testCase, group, turns, sessionId, cleanup) {
  const finalTurn = turns[turns.length - 1] || null;
  const durations = turns.map((turn) => turn.duration_ms).filter(Number.isFinite);
  const selectedTools = turns.map((turn) => turn.ab_test?.selected_tool || turn.tool).filter(Boolean);
  const routeFlipCount = selectedTools.reduce((count, tool, index) => {
    if (index === 0) return 0;
    return count + (tool !== selectedTools[index - 1] ? 1 : 0);
  }, 0);
  const vehicleExpertHit = turns.some(
    (turn) => (turn.ab_test?.selected_tool || turn.tool) === 'consult_vehicle_expert'
  );
  const askedForMoreInfo = turns.some((turn) => turn.asks_for_more_info);
  const emptyResponse = turns.some((turn) => turn.empty_response);
  const failed = turns.some((turn) => turn.status === 'error') || emptyResponse;
  const contextDrift = false;
  const boundaryMisroute =
    testCase.scenario_type === 'boundary_exception' &&
    turns.some((turn) => (turn.ab_test?.selected_tool || turn.tool) === 'consult_vehicle_expert');

  return {
    group,
    session_id: sessionId,
    turn_count: turns.length,
    final_tool: finalTurn?.tool || null,
    asked_for_more_info: askedForMoreInfo,
    empty_response: emptyResponse,
    failed,
    vehicle_expert_hit: vehicleExpertHit,
    route_flip_count: routeFlipCount,
    context_drift: contextDrift,
    boundary_misroute: boundaryMisroute,
    total_duration_ms: durations.reduce((sum, value) => sum + value, 0),
    avg_duration_ms: mean(durations),
    p50_duration_ms: percentile(durations, 0.5),
    p95_duration_ms: percentile(durations, 0.95),
    final_excerpt: finalTurn?.content_excerpt || '',
    turns,
    cleanup,
  };
}

async function runGroupCase(api, testCase, group) {
  const title = `[assistant-ab] ${testCase.id} ${group} ${Date.now()}`;
  const sessionResult = await api.createSession(title);
  const session = unwrapData(sessionResult.data);
  const sessionId = session?.id;

  if (!sessionId) {
    throw new Error(`create_session_missing_id ${testCase.id} ${group}`);
  }

  const turns = [];
  let cleanup = { deleted: false, error: null };

  try {
    for (const prompt of testCase.turns) {
      try {
        const chatResult = await api.chat(sessionId, prompt, group);
        turns.push({ status: 'ok', ...summarizeTurn(testCase, group, prompt, chatResult) });
      } catch (error) {
        turns.push({
          status: 'error',
          prompt,
          group,
          duration_ms: null,
          message_id: null,
          content_excerpt: '',
          content_length: 0,
          asks_for_more_info: false,
          empty_response: true,
          tool: null,
          ab_test: null,
          error: safeError(error),
          should_ask_for_info: testCase.should_ask_for_info,
        });
        break;
      }
    }
  } finally {
    try {
      await api.deleteSession(sessionId);
      cleanup = { deleted: true, error: null };
    } catch (error) {
      cleanup = { deleted: false, error: safeError(error) };
    }
  }

  return aggregateGroupResult(testCase, group, turns, sessionId, cleanup);
}

function buildComparison(testCase, xResult, yResult) {
  const differenceFlags = [];
  const problemTags = [];

  if (xResult.final_tool !== yResult.final_tool) differenceFlags.push('tool_diff');
  if (xResult.asked_for_more_info !== yResult.asked_for_more_info) differenceFlags.push('followup_diff');
  if (xResult.failed || yResult.failed) differenceFlags.push('failure_present');

  if (xResult.failed) problemTags.push('x_failed');
  if (yResult.failed) problemTags.push('y_failed');
  if (xResult.boundary_misroute) problemTags.push('x_boundary_misroute');
  if (yResult.boundary_misroute) problemTags.push('y_boundary_misroute');
  if (xResult.context_drift) problemTags.push('x_context_drift');
  if (yResult.context_drift) problemTags.push('y_context_drift');
  if (testCase.should_ask_for_info === true && !xResult.asked_for_more_info) problemTags.push('x_missing_followup');
  if (testCase.should_ask_for_info === true && !yResult.asked_for_more_info) problemTags.push('y_missing_followup');
  if (yResult.vehicle_expert_hit && testCase.scenario_type === 'boundary_exception') {
    problemTags.push('y_misrouted_to_vehicle_expert');
  }

  const yClearWin =
    ['complex_analysis', 'multi_turn'].includes(testCase.scenario_type) &&
    !yResult.failed &&
    !yResult.asked_for_more_info &&
    (xResult.failed || xResult.asked_for_more_info);
  const xClearWin =
    !xResult.failed &&
    !xResult.asked_for_more_info &&
    (yResult.failed || yResult.asked_for_more_info);

  if (yClearWin) differenceFlags.push('y_clear_win');
  if (xClearWin) differenceFlags.push('x_clear_win');

  return {
    case_id: testCase.id,
    scenario_type: testCase.scenario_type,
    prompt: testCase.turns[0],
    focus: testCase.focus,
    x: xResult,
    y: yResult,
    difference_flags: differenceFlags,
    problem_tags: unique(problemTags),
  };
}

function aggregateScenarioMetrics(caseComparisons, scenarioType, groupKey) {
  const groupResults = caseComparisons
    .filter((item) => item.scenario_type === scenarioType)
    .map((item) => item[groupKey]);
  const durations = groupResults.flatMap((item) => item.turns.map((turn) => turn.duration_ms).filter(Number.isFinite));

  return {
    cases: groupResults.length,
    vehicle_expert_hit_rate: groupResults.length
      ? Number((groupResults.filter((item) => item.vehicle_expert_hit).length / groupResults.length).toFixed(3))
      : 0,
    failure_rate: groupResults.length
      ? Number((groupResults.filter((item) => item.failed).length / groupResults.length).toFixed(3))
      : 0,
    empty_rate: groupResults.length
      ? Number((groupResults.filter((item) => item.empty_response).length / groupResults.length).toFixed(3))
      : 0,
    ask_more_info_rate: groupResults.length
      ? Number((groupResults.filter((item) => item.asked_for_more_info).length / groupResults.length).toFixed(3))
      : 0,
    context_drift_rate: groupResults.length
      ? Number((groupResults.filter((item) => item.context_drift).length / groupResults.length).toFixed(3))
      : 0,
    boundary_misroute_rate: groupResults.length
      ? Number((groupResults.filter((item) => item.boundary_misroute).length / groupResults.length).toFixed(3))
      : 0,
    avg_duration_ms: mean(durations),
    p50_duration_ms: percentile(durations, 0.5),
    p95_duration_ms: percentile(durations, 0.95),
  };
}

function buildSummary(caseComparisons, statsProbe) {
  const scenarioTypes = unique(caseComparisons.map((item) => item.scenario_type));
  const scenarios = Object.fromEntries(
    scenarioTypes.map((scenarioType) => [
      scenarioType,
      {
        X: aggregateScenarioMetrics(caseComparisons, scenarioType, 'x'),
        Y: aggregateScenarioMetrics(caseComparisons, scenarioType, 'y'),
      },
    ])
  );

  const complexCases = caseComparisons.filter((item) =>
    ['complex_analysis', 'multi_turn'].includes(item.scenario_type)
  );
  const simpleCases = caseComparisons.filter((item) =>
    ['basic_query', 'explain_diagnose'].includes(item.scenario_type)
  );
  const boundaryCases = caseComparisons.filter((item) => item.scenario_type === 'boundary_exception');

  const yClearWins = complexCases.filter((item) => item.difference_flags.includes('y_clear_win')).length;
  const xClearWins = caseComparisons.filter((item) => item.difference_flags.includes('x_clear_win')).length;
  const yBoundaryMisroutes = boundaryCases.filter((item) => item.y.boundary_misroute).length;
  const xBoundaryMisroutes = boundaryCases.filter((item) => item.x.boundary_misroute).length;
  const yFailures = caseComparisons.filter((item) => item.y.failed).length;
  const xFailures = caseComparisons.filter((item) => item.x.failed).length;
  const ySimpleSlower = simpleCases.filter((item) => {
    const x = item.x.avg_duration_ms ?? 0;
    const y = item.y.avg_duration_ms ?? 0;
    return x > 0 && y > x * 1.5;
  }).length;

  let recommendation = 'rollback_y';
  const reasons = [];

  if (yClearWins >= 3 && yFailures <= xFailures && yBoundaryMisroutes <= xBoundaryMisroutes) {
    recommendation = 'keep_y';
    reasons.push('Y shows repeated wins in complex or multi-turn scenarios.');
    reasons.push('Y does not increase failure or boundary-misroute cost.');
  } else if (yClearWins >= 1 && (yBoundaryMisroutes > xBoundaryMisroutes || ySimpleSlower > 0 || yFailures > xFailures)) {
    recommendation = 'partial_keep_y';
    reasons.push('Y helps in some complex scenarios but costs more in simple or boundary cases.');
  } else {
    reasons.push('Y benefit is unstable or too small to cover failure and boundary cost.');
  }

  if (yClearWins === 0) reasons.push('No clear Y win was found in complex-analysis cases.');
  if (yBoundaryMisroutes > xBoundaryMisroutes) reasons.push('Y has more boundary misroutes into vehicle_expert.');
  if (yFailures > xFailures) reasons.push('Y has more failed samples than X.');
  if (ySimpleSlower > 0) reasons.push('Y is materially slower in part of the simple-case set.');
  if (xClearWins > 0) reasons.push(`X clear-win samples: ${xClearWins}.`);

  return {
    recommendation,
    reasons: unique(reasons),
    totals: {
      cases: caseComparisons.length,
      y_clear_wins: yClearWins,
      x_clear_wins: xClearWins,
      y_failures: yFailures,
      x_failures: xFailures,
      y_boundary_misroutes: yBoundaryMisroutes,
      x_boundary_misroutes: xBoundaryMisroutes,
    },
    scenarios,
    stats_probe: statsProbe,
  };
}

function renderMarkdown(run) {
  const lines = [];
  lines.push('# Assistant A/B Playwright Report');
  lines.push('');
  lines.push(`- Round: \`${run.config.round}\``);
  lines.push(`- Assistant URL: \`${run.config.assistantUrl}\``);
  lines.push(`- API Base URL: \`${run.runtime.apiBaseUrl}\``);
  lines.push(`- Cases: \`${run.summary.totals.cases}\``);
  lines.push(`- Recommendation: **${run.summary.recommendation}**`);
  lines.push('');

  if (run.summary.reasons.length) {
    lines.push('## Decision Basis');
    for (const reason of run.summary.reasons) {
      lines.push(`- ${reason}`);
    }
    lines.push('');
  }

  if (run.summary.stats_probe) {
    lines.push('## Stats Probe');
    lines.push(`- Stats panel visible: \`${run.runtime.statsVisible}\``);
    lines.push(`- Before sample_turns: \`${run.summary.stats_probe.before?.sample_turns ?? 'n/a'}\``);
    lines.push(`- After sample_turns: \`${run.summary.stats_probe.after?.sample_turns ?? 'n/a'}\``);
    lines.push(`- Restored sample_turns: \`${run.summary.stats_probe.restored?.sample_turns ?? 'n/a'}\``);
    lines.push('');
  }

  lines.push('## Scenario Metrics');
  lines.push('');
  lines.push('| Scenario | Group | Cases | Vehicle Chain Hit | Failure | Ask More Info | Context Drift | Boundary Misroute | Avg ms | P95 ms |');
  lines.push('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|');
  for (const [scenarioType, groups] of Object.entries(run.summary.scenarios)) {
    for (const groupKey of ['X', 'Y']) {
      const metrics = groups[groupKey];
      lines.push(
        `| ${scenarioType} | ${groupKey} | ${metrics.cases} | ${metrics.vehicle_expert_hit_rate} | ${metrics.failure_rate} | ${metrics.ask_more_info_rate} | ${metrics.context_drift_rate} | ${metrics.boundary_misroute_rate} | ${metrics.avg_duration_ms ?? '-'} | ${metrics.p95_duration_ms ?? '-'} |`
      );
    }
  }
  lines.push('');

  lines.push('## Case Highlights');
  lines.push('');
  lines.push('| Case | Scenario | X Route | Y Route | Flags | Problem Tags |');
  lines.push('|---|---|---|---|---|---|');
  for (const item of run.cases) {
    lines.push(
      `| ${item.case_id} | ${item.scenario_type} | ${item.x.final_tool ?? '-'} | ${item.y.final_tool ?? '-'} | ${item.difference_flags.join(', ') || '-'} | ${item.problem_tags.join(', ') || '-'} |`
    );
  }

  return `${lines.join('\n')}\n`;
}

async function writeOutputs(outputDir, run) {
  const stamp = nowStamp();
  const jsonPath = path.join(outputDir, `${stamp}.json`);
  const mdPath = path.join(outputDir, `${stamp}.md`);
  const latestJsonPath = path.join(outputDir, 'latest.json');
  const latestMdPath = path.join(outputDir, 'latest.md');
  const markdown = renderMarkdown(run);
  const jsonText = JSON.stringify(run, null, 2);

  await fs.writeFile(jsonPath, jsonText);
  await fs.writeFile(mdPath, markdown);
  await fs.writeFile(latestJsonPath, jsonText);
  await fs.writeFile(latestMdPath, markdown);

  return { jsonPath, mdPath, latestJsonPath, latestMdPath };
}

async function runStatsProbe(api, enabled) {
  if (!enabled) return null;

  const before = simplifyStats((await api.getStats()).data);
  let xSessionId = null;
  let ySessionId = null;
  let after = null;
  let restored = null;

  try {
    xSessionId = unwrapData((await api.createSession('[stats-probe] X')).data)?.id || null;
    if (xSessionId) await api.chat(xSessionId, statsProbePrompt, 'X');

    ySessionId = unwrapData((await api.createSession('[stats-probe] Y')).data)?.id || null;
    if (ySessionId) await api.chat(ySessionId, statsProbePrompt, 'Y');

    after = simplifyStats((await api.getStats()).data);
  } finally {
    if (xSessionId) {
      try {
        await api.deleteSession(xSessionId);
      } catch {}
    }
    if (ySessionId) {
      try {
        await api.deleteSession(ySessionId);
      } catch {}
    }
    try {
      restored = simplifyStats((await api.getStats()).data);
    } catch {
      restored = null;
    }
  }

  return { before, after, restored };
}

async function main() {
  const config = {
    assistantUrl: process.env.ASSISTANT_URL || defaultAssistantUrl,
    apiBaseUrl: process.env.ASSISTANT_API_BASE_URL || '',
    username: process.env.ASSISTANT_USERNAME || '',
    password: process.env.ASSISTANT_PASSWORD || '',
    headless: envBoolean(process.env.ASSISTANT_HEADLESS, true),
    timeoutMs: envNumber(process.env.ASSISTANT_TIMEOUT_MS, 45000),
    outputDir: process.env.ASSISTANT_OUTPUT_DIR || defaultOutputDir,
    round: process.env.ASSISTANT_ROUND || 'round1',
    caseFilter: process.env.ASSISTANT_CASE_FILTER || '',
    caseLimit: envNumber(process.env.ASSISTANT_CASE_LIMIT, 0),
    browserChannel: process.env.ASSISTANT_BROWSER_CHANNEL || '',
  };

  const cases = await loadCases(config);
  if (!cases.length) {
    throw new Error('no_cases_selected');
  }

  await ensureOutputDir(config.outputDir);

  const browser = await chromium.launch({
    headless: config.headless,
    channel: config.browserChannel || undefined,
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    const runtime = await loginToAssistant(page, config);
    const api = new AssistantApi(context.request, runtime.apiBaseUrl, config.timeoutMs);
    const me = unwrapData((await api.authMe()).data);
    const statsProbe = await runStatsProbe(api, runtime.statsVisible);

    const results = [];
    for (const testCase of cases) {
      const x = await runGroupCase(api, testCase, 'X');
      const y = await runGroupCase(api, testCase, 'Y');
      results.push(buildComparison(testCase, x, y));
    }

    const summary = buildSummary(results, statsProbe);
    const run = {
      generated_at: new Date().toISOString(),
      config: {
        ...config,
        password: config.password ? '***' : '',
      },
      runtime: {
        apiBaseUrl: runtime.apiBaseUrl,
        statsVisible: runtime.statsVisible,
        user: {
          id: me?.user?.id || null,
          username: me?.user?.username || null,
          role: me?.role || null,
          display_name: me?.user?.display_name || null,
        },
      },
      summary,
      cases: results,
    };

    const outputs = await writeOutputs(config.outputDir, run);

    console.log(
      JSON.stringify(
        {
          recommendation: summary.recommendation,
          cases: results.length,
          output: outputs,
        },
        null,
        2
      )
    );
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ error: safeError(error) }, null, 2));
  process.exitCode = 1;
});
