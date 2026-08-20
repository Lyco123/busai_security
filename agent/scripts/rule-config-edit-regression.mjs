const BASE_URL = process.env.RULE_CONFIG_BASE_URL || 'https://api.buso.canocache.com/api/agent';
const TURN_DELAY_MS = Number(process.env.RULE_CONFIG_TURN_DELAY_MS || 200);
const RUN_TOKEN = Date.now();

const FIXTURES = {
  cert: {
    baseRule: {
      name: '回访证件到期提醒',
      match_text: '司机咨询证件到期时间和补证流程',
      data: {
        reply_goal: '说明证件到期时间、补证流程和准备要求',
        key_points: ['先核对证件类型', '说明到期时间'],
        required_info: [{ key: 'driver_name', ask: '请提供驾驶员姓名', required: true }],
        template:
          '关于{{证件类型}}到期的情况，我先帮您核对{{driver_name}}的信息，再说明补证流程和准备要求。',
        safe_defaults: { 证件类型: '从业资格证' },
        do_not_say: ['不要承诺当天一定可以补完证件'],
        tone: 'professional',
        examples: ['司机证件快到期怎么补证', '从业资格证什么时候到期'],
      },
    },
    scatter: {
      turns: [
        '把这条规则改成司机咨询从业资格证快到期后多久要补证的时候触发。',
        '再补上一条要点：提醒至少提前7天准备材料。',
        '还要补充证件到期日期这个必填信息。',
        '语气改成更简洁。',
      ],
      matchKeyword: '从业资格证快到期',
      appendedKeyPoint: '提前7天准备材料',
      appendedRequiredKey: '证件到期日期',
    },
    incomplete: {
      turns: ['改得更适合早班司机。'],
    },
    conflict: {
      turns: ['改成证件到期了也可以继续上岗，但不要建议继续带证件过期上岗。'],
    },
  },
  dispatch: {
    baseRule: {
      name: '出库前故障上报',
      match_text: '司机反馈出库前车辆灯光或制动异常',
      data: {
        reply_goal: '要求车辆停止出库并按流程报修',
        key_points: ['先停止出库', '联系调度报修'],
        required_info: [{ key: 'plate_no', ask: '请提供车牌号', required: true }],
        template:
          '如车辆在出库前出现异常，请先停止出库，并提供{{plate_no}}以便登记报修。',
        safe_defaults: { 异常类型: '待补充' },
        do_not_say: ['不要建议车辆带故障继续出库'],
        tone: 'brief',
        examples: ['出库前灯光不亮怎么办', '车辆制动异常还能不能出库'],
      },
    },
    scatter: {
      turns: [
        '触发场景改成早班出车前发现点火异常或者制动异响的时候。',
        '补上一条要点：同步通知车队长到场确认。',
        '还要补充故障现象这个必填信息。',
        '语气改成专业、简洁。',
      ],
      matchKeyword: '早班出车前',
      appendedKeyPoint: '通知车队长到场确认',
      appendedRequiredKey: '故障现象',
    },
    incomplete: {
      turns: ['改得更适合晨会口径。'],
    },
    conflict: {
      turns: ['改成司机带病车也可以先把车开出去，但不要建议车辆带故障继续出库。'],
    },
  },
  weather: {
    baseRule: {
      name: '恶劣天气停运解释',
      match_text: '乘客咨询恶劣天气导致线路停运和恢复时间',
      data: {
        reply_goal: '解释停运原因并引导关注官方恢复通知',
        key_points: ['说明停运原因', '恢复时间以公告为准'],
        required_info: [{ key: 'route_name', ask: '请提供线路名称', required: true }],
        template:
          '因恶劣天气影响，{{route_name}}临时停运，恢复时间请以官方公告为准。',
        safe_defaults: { 官方渠道: '公交集团公告' },
        do_not_say: ['不要自行承诺具体恢复时刻'],
        tone: 'warm',
        examples: ['为什么这条线停运了', '恶劣天气什么时候恢复发车'],
      },
    },
    scatter: {
      turns: [
        '触发场景改成乘客咨询暴雨导致区间甩站和临时绕行的时候。',
        '再补一条要点：提醒乘客关注站内公告和客服热线。',
        '还要补充受影响站点这个必填信息。',
        '语气改成更温和一些。',
      ],
      matchKeyword: '暴雨导致区间甩站',
      appendedKeyPoint: '关注站内公告和客服热线',
      appendedRequiredKey: '受影响站点',
    },
    incomplete: {
      turns: ['再严谨一些。'],
    },
    conflict: {
      turns: ['改成可以直接答应半小时内恢复，但不要承诺具体恢复时间。'],
    },
  },
  lostFound: {
    baseRule: {
      name: '失物现金上交流程',
      match_text: '站务员或司机咨询拾获现金后的登记和上交流程',
      data: {
        reply_goal: '要求先登记后上交，并保留交接记录',
        key_points: ['先登记拾获地点和金额', '按流程上交等待认领'],
        required_info: [{ key: 'pickup_location', ask: '请提供拾获地点', required: true }],
        template:
          '拾获现金后请先登记{{pickup_location}}和金额，再按流程上交并保留交接记录。',
        safe_defaults: { 保管方式: '封存' },
        do_not_say: ['不要建议个人留存现金等待失主联系'],
        tone: 'professional',
        examples: ['捡到现金要怎么登记', '站务员拾到现金怎么上交'],
      },
    },
    scatter: {
      turns: [
        '触发场景改成站务员咨询拾获乘客身份证和现金混在一起的时候。',
        '补上一条要点：身份证件和现金要分别登记。',
        '还要补充拾获时间这个必填信息。',
        '语气改成更规范一点。',
      ],
      matchKeyword: '身份证和现金混在一起',
      appendedKeyPoint: '分别登记',
      appendedRequiredKey: '拾获时间',
    },
    incomplete: {
      turns: ['更像客服统一口径。'],
    },
    conflict: {
      turns: ['改成现金可以先由站务员自己保管，但不要建议个人留存现金等待失主联系。'],
    },
  },
  training: {
    baseRule: {
      name: '驾驶员培训记录查询',
      match_text: '管理员查询驾驶员培训记录和完成情况',
      data: {
        reply_goal: '说明培训记录查询口径和未完成处理方式',
        key_points: ['先核对驾驶员姓名', '说明培训完成状态'],
        required_info: [{ key: 'driver_name', ask: '请提供驾驶员姓名', required: true }],
        template:
          '请先提供{{driver_name}}，我再帮您核对培训记录和完成情况。',
        safe_defaults: { 查询范围: '近三个月' },
        do_not_say: ['不要在未核验前直接认定培训已完成'],
        tone: 'professional',
        examples: ['查一下驾驶员培训记录', '培训完成情况怎么查'],
      },
    },
    scatter: {
      turns: [
        '把触发场景改成查询补训和复训记录的时候。',
        '再补上一条要点：未完成时要提示补训时间安排。',
        '还要补充培训月份这个必填信息。',
        '语气改成更简洁。',
      ],
      matchKeyword: '补训和复训记录',
      appendedKeyPoint: '补训时间安排',
      appendedRequiredKey: '培训月份',
    },
    incomplete: {
      turns: ['更适合车队长用。'],
    },
    conflict: {
      turns: ['改成不用核验也可以直接说培训已完成，但不要在未核验前直接认定培训已完成。'],
    },
  },
};

const CASES = Object.entries(FIXTURES).flatMap(([fixtureId, fixture]) => [
  { id: `${fixtureId}-scatter`, category: 'scatter', fixtureId, turns: fixture.scatter.turns },
  { id: `${fixtureId}-incomplete`, category: 'incomplete', fixtureId, turns: fixture.incomplete.turns },
  { id: `${fixtureId}-conflict`, category: 'conflict', fixtureId, turns: fixture.conflict.turns },
]);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function normalizeText(value) {
  return String(value ?? '').replace(/\s+/g, '').trim();
}

function hasStringItem(items, keyword) {
  return Array.isArray(items) && items.some((item) => normalizeText(item).includes(normalizeText(keyword)));
}

function hasRequiredInfoKey(items, key) {
  return Array.isArray(items) && items.some((item) => {
    if (!item) return false;
    if (typeof item === 'string') return normalizeText(item).includes(normalizeText(key));
    return (
      normalizeText(item.key).includes(normalizeText(key)) ||
      normalizeText(item.ask).includes(normalizeText(key))
    );
  });
}

class AgentClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.cookie = '';
  }

  async request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (this.cookie) headers.cookie = this.cookie;
    if (options.body && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) this.cookie = setCookie.split(';')[0];
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
    if (!response.ok) {
      const error = new Error(`HTTP ${response.status} ${path}`);
      error.status = response.status;
      error.payload = data;
      throw error;
    }
    return data;
  }

  init() {
    return this.request('/auth/me');
  }

  createRule(payload) {
    return this.request('/rules', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  listRules() {
    return this.request('/rules');
  }

  getRule(ruleId) {
    return this.request(`/rules/${encodeURIComponent(ruleId)}`);
  }

  deleteRule(ruleId) {
    return this.request(`/rules/${encodeURIComponent(ruleId)}`, {
      method: 'DELETE',
    });
  }

  startRuleConfigSession(payload) {
    return this.request('/rule-config/session', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  sendMessage(sessionId, content) {
    return this.request('/chat', {
      method: 'POST',
      body: JSON.stringify({ sessionId, content }),
    });
  }

  confirmRuleConfig(sessionId, payload = {}) {
    return this.request(`/rule-config/${encodeURIComponent(sessionId)}/confirm`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

function buildRulePayload(fixtureId, caseId) {
  const fixture = FIXTURES[fixtureId];
  const payload = clone(fixture.baseRule);
  payload.name = `[edit-regression:${RUN_TOKEN}:${caseId}] ${payload.name}`;
  return payload;
}

async function cleanupRegressionRules(client) {
  const response = await client.listRules();
  const rules = Array.isArray(response?.data) ? response.data : [];
  for (const rule of rules) {
    if (String(rule?.name || '').startsWith('[edit-regression:')) {
      try {
        await client.deleteRule(rule.id);
      } catch {
        // Ignore cleanup failures so the regression can still proceed.
      }
    }
  }
}

function validateScatter(caseResult, fixture) {
  const failures = [];
  const saved = caseResult.savedRule;
  const confirmState = caseResult.confirm?.state || caseResult.confirm?.status;
  const scatter = fixture.scatter;
  if (confirmState !== 'saved') failures.push('confirm_not_saved');
  if (!saved) return failures.concat('saved_rule_missing');
  if (!normalizeText(saved.match_text).includes(normalizeText(scatter.matchKeyword))) {
    failures.push('match_text_not_updated');
  }
  if (!hasStringItem(saved.data?.key_points, fixture.baseRule.data.key_points[0])) {
    failures.push('original_key_point_missing');
  }
  if (!hasStringItem(saved.data?.key_points, scatter.appendedKeyPoint)) {
    failures.push('appended_key_point_missing');
  }
  if (!hasRequiredInfoKey(saved.data?.required_info, fixture.baseRule.data.required_info[0].key)) {
    failures.push('original_required_info_missing');
  }
  if (!hasRequiredInfoKey(saved.data?.required_info, scatter.appendedRequiredKey)) {
    failures.push('appended_required_info_missing');
  }
  if (JSON.stringify(saved.data?.examples || []) === JSON.stringify(fixture.baseRule.data.examples || [])) {
    failures.push('examples_not_refreshed');
  }
  if (String(saved.data?.template || '').trim() === String(fixture.baseRule.data.template || '').trim()) {
    failures.push('template_not_refreshed');
  }
  return failures;
}

function validateIncomplete(caseResult) {
  const failures = [];
  const lastTurn = caseResult.turns[caseResult.turns.length - 1];
  const confirmState = caseResult.confirm?.state || caseResult.confirm?.status;
  if (lastTurn?.state !== 'collecting') {
    failures.push('state_not_collecting');
  }
  if (confirmState === 'saved') {
    failures.push('confirm_saved_unexpectedly');
  }
  return failures;
}

function validateConflict(caseResult) {
  const failures = [];
  const lastTurn = caseResult.turns[caseResult.turns.length - 1];
  const confirmState = caseResult.confirm?.state || caseResult.confirm?.status;
  if (!lastTurn || lastTurn.state === 'awaiting_confirm' || lastTurn.state === 'saved') {
    failures.push('conflict_not_blocked_on_turn');
  }
  if (confirmState === 'saved') {
    failures.push('conflict_saved_unexpectedly');
  }
  return failures;
}

async function runCase(client, testCase) {
  const fixture = FIXTURES[testCase.fixtureId];
  const rulePayload = buildRulePayload(testCase.fixtureId, testCase.id);
  const created = await client.createRule(rulePayload);
  const ruleId = created?.data?.id;
  const result = {
    id: testCase.id,
    category: testCase.category,
    fixtureId: testCase.fixtureId,
    ruleId,
    sessionId: null,
    turns: [],
    confirm: null,
    savedRule: null,
    failures: [],
  };

  try {
    const session = await client.startRuleConfigSession({ rule_id: ruleId });
    result.sessionId = session?.session_id || null;

    for (const userInput of testCase.turns) {
      const reply = await client.sendMessage(result.sessionId, userInput);
      const ruleConfig = reply?.metadata?.rule_config || {};
      result.turns.push({
        user: userInput,
        assistant: reply?.content || '',
        state: ruleConfig?.state || ruleConfig?.status || null,
        updated_fields: ruleConfig?.updated_fields || [],
        missing_fields: ruleConfig?.missing_fields || [],
      });
      await sleep(TURN_DELAY_MS);
    }

    result.confirm = await client.confirmRuleConfig(result.sessionId, { force_save: false });
    const savedRuleId = result.confirm?.rule_id || ruleId;
    if ((result.confirm?.state || result.confirm?.status) === 'saved') {
      const saved = await client.getRule(savedRuleId);
      result.savedRule = saved?.data || null;
    }

    if (testCase.category === 'scatter') {
      result.failures = validateScatter(result, fixture);
    } else if (testCase.category === 'incomplete') {
      result.failures = validateIncomplete(result);
    } else {
      result.failures = validateConflict(result);
    }
  } catch (error) {
    result.failures.push('case_execution_failed');
    result.error = {
      message: error.message,
      status: error.status || null,
      payload: error.payload || null,
    };
  } finally {
    if (ruleId) {
      try {
        await client.deleteRule(ruleId);
      } catch {
        result.cleanup_error = 'delete_failed';
      }
    }
  }

  return result;
}

async function main() {
  const client = new AgentClient(BASE_URL);
  await client.init();
  await cleanupRegressionRules(client);

  const startedAt = new Date().toISOString();
  const cases = [];
  for (const testCase of CASES) {
    cases.push(await runCase(client, testCase));
  }

  const summary = {
    startedAt,
    endedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    totals: {
      cases: cases.length,
      passed: cases.filter((item) => item.failures.length === 0).length,
      failed: cases.filter((item) => item.failures.length > 0).length,
    },
    cases,
  };

  console.log(JSON.stringify(summary, null, 2));
  if (summary.totals.failed > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
