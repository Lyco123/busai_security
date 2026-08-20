const BASE_URL = process.env.RULE_CONFIG_BASE_URL || 'https://api.buso.canocache.com/api/agent';

const CASES = [
  {
    id: 'scatter-01',
    category: '信息分散',
    title: '驾驶员证件到期提醒',
    turns: [
      '我想先做一条规则，和司机证件快到期有关。',
      '大概是车队长来问哪个司机证件快到期、什么时候该换证的时候触发。',
      '回复里要说明到期时间、补证流程、提前多久提醒。',
      '还得问驾驶员姓名和证件类型，语气专业。',
    ],
  },
  {
    id: 'scatter-02',
    category: '信息分散',
    title: '车辆出库前故障上报',
    turns: [
      '要做个规则，给早班出车前用。',
      '如果司机说车子点火异常、灯光不亮或者制动有问题，就要触发。',
      '回复要先提醒停止出库，再说报修和联系调度。',
      '需要补车牌号和故障现象，语气简洁。',
    ],
  },
  {
    id: 'scatter-03',
    category: '信息分散',
    title: '恶劣天气停运解释',
    turns: [
      '帮我配一个规则，跟天气停运解释有关。',
      '就是乘客问为什么这条线临时停运、什么时候恢复的时候触发。',
      '回复要说明停运原因、恢复以公告为准、建议关注官方渠道。',
      '需要知道线路名称，语气温和。',
    ],
  },
  {
    id: 'scatter-04',
    category: '信息分散',
    title: '场站充电桩故障上报',
    turns: [
      '我这边还想做一个场站设备类规则。',
      '如果司机或者站务说充电桩故障、插枪没反应、充不上电的时候触发。',
      '回复要告诉他先停止使用、报给机务、等现场确认。',
      '需要站点名称和设备编号，语气专业。',
    ],
  },
  {
    id: 'scatter-05',
    category: '信息分散',
    title: '班前酒测异常处置',
    turns: [
      '再来一个和班前检查有关的规则。',
      '如果管理人员问酒测异常怎么处理、司机自己报酒测不过的时候触发。',
      '回复里要写暂停上岗、安排复测、同步车队负责人。',
      '需要驾驶员姓名和检测时间，语气专业。',
    ],
  },
  {
    id: 'guide-01',
    category: '用户不了解系统',
    title: '驾驶员请假顶班申请',
    turns: [
      '最近司机请假顶班这个事老是问到我，你给我弄个统一说法。',
      '反正就是谁想换班顶班，别直接私下换，要走审批。',
      '你就告诉他们先报日期和班次，再让车队长批。',
      '还要问驾驶员姓名，语气温和一点。',
    ],
  },
  {
    id: 'guide-02',
    category: '用户不了解系统',
    title: '新能源车续航不足上报',
    turns: [
      '新能源车老有人说电不够跑完全程，这个你给我做一个说法。',
      '别讲太复杂，就告诉他们先看剩余电量，不行就联系调度换车。',
      '最好把线路和车牌先问出来。',
      '语气简洁，别吓人。',
    ],
  },
  {
    id: 'guide-03',
    category: '用户不了解系统',
    title: '刷卡异常解释',
    turns: [
      '乘客老说刷卡机有问题，你帮我弄一个统一回复。',
      '大概就是卡刷不上、重复扣费、二维码识别慢这种情况。',
      '回复里要先致歉，再告诉他保留乘车时间和线路，后面核查。',
      '需要线路名称和乘车时间，语气温和。',
    ],
  },
  {
    id: 'guide-04',
    category: '用户不了解系统',
    title: '拾获现金上交流程',
    turns: [
      '站务员捡到现金以后老来问我怎么交，你帮我规范一下。',
      '意思就是别自己留着，要登记、上交、等失主认领。',
      '回复里要写明登记和交接流程。',
      '需要拾获地点和金额，语气专业。',
    ],
  },
  {
    id: 'guide-05',
    category: '用户不了解系统',
    title: '班前安全例会迟到说明',
    turns: [
      '班前安全会迟到这个事情，帮我做一个统一话术。',
      '就是有人问迟到了怎么报备、还能不能上岗。',
      '你就告诉他们先和车队长说明，再按当班安排处理，别直接承诺能上岗。',
      '需要驾驶员姓名和班次，语气简洁。',
    ],
  },
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

  startRuleConfigSession(payload = {}) {
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

  getRule(ruleId) {
    return this.request(`/rules/${encodeURIComponent(ruleId)}`);
  }

  deleteRule(ruleId) {
    return this.request(`/rules/${encodeURIComponent(ruleId)}`, {
      method: 'DELETE',
    });
  }
}

function assertTurnConsistency(turn) {
  const failures = [];
  const text = String(turn.assistant || '');
  const updated = Array.isArray(turn.updated_fields) ? turn.updated_fields : [];
  const missing = Array.isArray(turn.missing_fields) ? turn.missing_fields : [];

  if (text.includes('已记录') && updated.length === 0) {
    failures.push('assistant_claimed_update_without_updated_fields');
  }
  if (text.includes('可确认') && turn.state !== 'awaiting_confirm') {
    failures.push('assistant_claimed_confirmable_without_state');
  }
  if (text.includes('可确认') && missing.length > 0) {
    failures.push('assistant_claimed_confirmable_with_missing_fields');
  }
  return failures;
}

async function runCase(client, testCase, options = {}) {
  const start = await client.startRuleConfigSession();
  const sessionId = start.session_id;
  const result = {
    id: testCase.id,
    category: testCase.category,
    title: testCase.title,
    sessionId,
    turns: [],
    confirm: null,
    savedRule: null,
    deleteResult: null,
    assertions: [],
  };

  for (const userInput of testCase.turns) {
    const reply = await client.sendMessage(sessionId, userInput);
    const ruleConfig = reply?.metadata?.rule_config || {};
    const turn = {
      user: userInput,
      assistant: reply?.content || '',
      state: ruleConfig?.state || ruleConfig?.status || null,
      updated_fields: ruleConfig?.updated_fields || [],
      missing_fields: ruleConfig?.missing_fields || [],
      rework_ticket: ruleConfig?.rework_ticket || null,
      draft: ruleConfig?.draft || null,
    };
    result.turns.push(turn);
    result.assertions.push(...assertTurnConsistency(turn).map((code) => ({ turn: userInput, code })));
    await sleep(options.turnDelayMs || 200);
  }

  try {
    const confirm = await client.confirmRuleConfig(sessionId, { force_save: false });
    result.confirm = confirm;
    if (confirm?.rule_id) {
      const rulePayload = await client.getRule(confirm.rule_id);
      result.savedRule = rulePayload?.data || null;
      if (options.cleanup !== false) {
        result.deleteResult = await client.deleteRule(confirm.rule_id);
      }
    }
  } catch (error) {
    result.confirm = {
      error: error.message,
      status: error.status || null,
      payload: error.payload || null,
    };
  }

  return result;
}

async function main() {
  const client = new AgentClient(BASE_URL);
  await client.init();

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
      saved: cases.filter((item) => item.confirm?.state === 'saved' || item.confirm?.status === 'saved').length,
      assertions_failed: cases.reduce((count, item) => count + item.assertions.length, 0),
    },
    cases,
  };

  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
