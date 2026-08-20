import type { WorkerRuntimeOptions } from './worker-runner';
import { collapseWhitespace, truncateText } from '../../shared/text';

interface OmniKbEnv {
  KB_API_BASE_URL?: string;
  KB_API_TIMEOUT_MS?: string;
  KB_DEFAULT_ID?: string;
  KB_TENANT_ID?: string;
}

interface OmniKbDebugMetadata {
  configured: boolean;
  kb_id: string;
  top_k: number;
  attempted: boolean;
  injected: boolean;
  hit_count: number;
  error?: string;
  gate: {
    should_retrieve: boolean;
    reason: string;
    matched_terms: string[];
  };
  hits: Array<{
    doc_id: string;
    clause_id?: string;
    title?: string;
    score?: number;
    heading_path?: string[];
  }>;
}

interface KbGateDecision {
  shouldRetrieve: boolean;
  reason: string;
  matchedTerms: string[];
}

const KB_DOCUMENT_PATTERN = /〔\d{4}〕\d+号|关于印发|校对稿|通知|规定|办法|细则|指引|制度|条例/;

const KB_POLICY_TERMS = [
  '规定',
  '办法',
  '制度',
  '条款',
  '依据',
  '适用于',
  '适用范围',
  '应当',
  '不得',
  '责任',
  '职责',
  '流程',
  '时限',
  '投诉',
  '受理',
  '调查',
  '处理',
  '分类',
  '认定',
  '消防',
  '隐患',
  '预案',
  '演练',
  '处罚',
  '附件',
];

const KB_BUSINESS_DATA_TERMS = [
  '风险评分',
  '风险分',
  '评分趋势',
  '趋势图',
  '画像',
  '排名',
  '排行榜',
  '统计',
  '数据',
  '明细',
  '列表',
  '最近',
  '最新',
  '车辆',
  '驾驶员',
  '司机',
  '线路',
  '站场',
  '单位',
];

function decideKbRetrieval(query: string): KbGateDecision {
  const normalized = collapseWhitespace(query);
  if (!normalized) {
    return { shouldRetrieve: false, reason: 'empty_query', matchedTerms: [] };
  }

  if (KB_DOCUMENT_PATTERN.test(normalized)) {
    return { shouldRetrieve: true, reason: 'document_or_policy_reference', matchedTerms: ['document_pattern'] };
  }

  const businessDataTerms = KB_BUSINESS_DATA_TERMS.filter((term) => normalized.includes(term));
  const matchedTerms = KB_POLICY_TERMS.filter((term) => normalized.includes(term));
  if (businessDataTerms.length > 0 && matchedTerms.length === 0) {
    return { shouldRetrieve: false, reason: 'business_data_intent', matchedTerms: businessDataTerms.slice(0, 8) };
  }
  if (matchedTerms.length > 0) {
    return { shouldRetrieve: true, reason: 'policy_terms', matchedTerms: matchedTerms.slice(0, 8) };
  }

  return { shouldRetrieve: false, reason: 'no_policy_intent', matchedTerms: [] };
}

function resolveKbTimeoutMs(env: OmniKbEnv): number {
  const value = Number(env.KB_API_TIMEOUT_MS ?? '20000');
  if (!Number.isFinite(value) || value <= 0) {
    return 20000;
  }
  return Math.floor(value);
}

function createKbRequestHeaders(env: OmniKbEnv, callerLevel: 'driver' | 'fleet' | 'company' | 'group' = 'group'): Headers {
  const headers = new Headers();
  headers.set('Content-Type', 'application/json; charset=utf-8');
  headers.set('X-Tenant-Id', String(env.KB_TENANT_ID || 'default'));
  headers.set('X-Caller-Level', callerLevel);
  headers.set('X-Caller-Id', 'agent-runtime');
  return headers;
}

type KbRetrieveItem = {
  doc_id: string;
  clause_id: string;
  field_path: string;
  heading_path: string[];
  content: string;
  score: number;
  min_level: 'driver' | 'fleet' | 'company' | 'group';
  metadata?: {
    title?: string;
    source_uri?: string;
    tags?: string[];
    file_name?: string;
    order_index?: number;
  };
};

function parseKbRetrieveItems(data: unknown): KbRetrieveItem[] {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return [];
  }
  const payload =
    data && typeof data === 'object' && !Array.isArray(data) && 'data' in data
      ? (data as { data?: unknown }).data
      : data;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return [];
  }
  const rawItems = (payload as { items?: unknown }).items;
  return Array.isArray(rawItems) ? (rawItems as KbRetrieveItem[]) : [];
}

function formatKbContextSnippet(query: string, items: KbRetrieveItem[]): string | null {
  if (!items.length) {
    return null;
  }

  const sections = items.slice(0, 4).map((item, index) => {
    const title = collapseWhitespace(String(item.metadata?.title || item.metadata?.file_name || item.doc_id || '未命名文档'));
    const heading = Array.isArray(item.heading_path)
      ? item.heading_path.map((part) => collapseWhitespace(String(part || ''))).filter(Boolean).join(' > ')
      : '';
    const content = truncateText(collapseWhitespace(String(item.content || '')), 280);
    const score = typeof item.score === 'number' && Number.isFinite(item.score) ? item.score.toFixed(3) : 'n/a';
    const pathLine = heading ? `标题路径: ${heading}` : `字段路径: ${String(item.field_path || '-')}`;
    return [
      `片段${index + 1}`,
      `来源文档: ${title}`,
      pathLine,
      `相关度: ${score}`,
      `内容: ${content}`,
    ].join('\n');
  });

  return [
    '以下知识库片段只作为额外参考信息，用于确认制度、规定、办法、条款、期限、频次或流程类事实。',
    '如果本轮还存在 MCP/业务数据工具结果或 report_source，具体车辆、驾驶员、线路、站场、单位的画像、评分、评价类型、日期、数量、状态、明细等业务事实必须以 MCP/业务数据工具结果或 report_source 为准；知识库片段不得覆盖、改写或补全这些业务字段。',
    '回答制度事实时，只能依据这些片段；片段没有覆盖的文件号、条款号、期限、频次、责任要求、保存年限、流程步骤，不得补充、猜测或用常识替代。',
    '如果片段只覆盖部分问题，请只回答已覆盖部分，并明确说明未覆盖部分当前无法从知识库确认。',
    '不要逐段照抄片段；请先整理、归纳，再自然回答。若使用了这些内容，请点明来源文档或条款位置。',
    `当前用户问题: ${truncateText(collapseWhitespace(query), 200)}`,
    '',
    sections.join('\n\n'),
  ].join('\n');
}

async function fetchKbRetrieve(env: OmniKbEnv, query: string, topK = 4): Promise<{ items: KbRetrieveItem[]; error?: string }> {
  const baseUrl = String(env.KB_API_BASE_URL ?? '').replace(/\/+$/, '');
  const normalizedQuery = collapseWhitespace(query);
  if (!baseUrl || !normalizedQuery) {
    return { items: [] };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), resolveKbTimeoutMs(env));

  try {
    const response = await fetch(`${baseUrl}/v1/retrieve`, {
      method: 'POST',
      headers: createKbRequestHeaders(env),
      body: JSON.stringify({
        kb_id: String(env.KB_DEFAULT_ID || 'regulations'),
        query: normalizedQuery,
        top_k: topK,
      }),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      return {
        items: [],
        error: (data as { error?: { message?: string } | string } | null)?.error instanceof Object
          ? ((data as { error?: { message?: string } }).error?.message ?? 'kb retrieve failed')
          : ((data as { error?: string } | null)?.error ?? 'kb retrieve failed'),
      };
    }
    return { items: parseKbRetrieveItems(data) };
  } catch (error) {
    return {
      items: [],
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timer);
  }
}

function buildKbDebugMetadata(
  env: OmniKbEnv,
  topK: number,
  kbResult: { items: KbRetrieveItem[]; error?: string },
  gate: KbGateDecision,
  attempted: boolean
): OmniKbDebugMetadata {
  const kbId = String(env.KB_DEFAULT_ID || 'regulations');
  const configured = Boolean(String(env.KB_API_BASE_URL ?? '').replace(/\/+$/, ''));
  return {
    configured,
    kb_id: kbId,
    top_k: topK,
    attempted: configured && attempted,
    injected: kbResult.items.length > 0,
    hit_count: kbResult.items.length,
    ...(kbResult.error ? { error: kbResult.error } : {}),
    gate: {
      should_retrieve: gate.shouldRetrieve,
      reason: gate.reason,
      matched_terms: gate.matchedTerms,
    },
    hits: kbResult.items.slice(0, topK).map((item) => ({
      doc_id: String(item.doc_id || ''),
      ...(item.clause_id ? { clause_id: String(item.clause_id) } : {}),
      ...(item.metadata?.title || item.metadata?.file_name
        ? { title: String(item.metadata.title || item.metadata.file_name) }
        : {}),
      ...(typeof item.score === 'number' && Number.isFinite(item.score) ? { score: item.score } : {}),
      ...(Array.isArray(item.heading_path) ? { heading_path: item.heading_path.map(String) } : {}),
    })),
  };
}

function buildKbSoftGuardrail(kbResult: { items: KbRetrieveItem[]; error?: string }, gate: KbGateDecision): string | null {
  if (!gate.shouldRetrieve || kbResult.items.length > 0) {
    return null;
  }

  const reason = kbResult.error ? `知识库检索失败：${kbResult.error}` : '知识库未检索到相关制度条款';
  return [
    '知识库软护栏',
    reason,
    '知识库只是额外参考信息，未命中或检索失败时不得阻断主流程。',
    '如果用户问题属于业务数据查询、画像、风险评分、趋势图、统计、列表或明细，请继续调用可用的 MCP/业务数据工具完成任务。',
    '如果用户明确询问制度依据、条款、流程、时限、责任或合规结论，只能说明当前知识库未提供依据，不得编造制度文件号、条款号或流程细节；但仍可回答非制度部分。',
  ].join('\n');
}

export async function buildOmniKbRuntimeOptions(
  env: OmniKbEnv,
  query: string,
  baseOptions?: WorkerRuntimeOptions
): Promise<WorkerRuntimeOptions | undefined> {
  const topK = 8;
  const gate = decideKbRetrieval(query);
  const kbResult = gate.shouldRetrieve ? await fetchKbRetrieve(env, query, topK) : { items: [] };
  const snippet = formatKbContextSnippet(query, kbResult.items);
  const softGuardrail = buildKbSoftGuardrail(kbResult, gate);
  const existingPrefix = baseOptions?.systemPromptPrefix?.trim();
  const metadata = {
    ...(baseOptions?.metadata ?? {}),
    omni_kb_debug: buildKbDebugMetadata(env, topK, kbResult, gate, gate.shouldRetrieve),
  };

  const prefixParts = [
    existingPrefix,
    snippet
      ? [
          '知识库增强上下文',
          snippet,
          '回答要求：这些片段只对制度、条款、流程、期限、频次、责任要求等制度事实构成约束。若回答涉及具体业务对象的数据事实，必须以 MCP/业务数据工具结果或 report_source 为准；知识库不得替代具体业务数据。无法由片段确认的制度内容必须明确说“当前知识库片段未覆盖，无法确认”，不要编造。',
        ].join('\n\n')
      : null,
    softGuardrail,
  ].filter((part): part is string => Boolean(part));

  return {
    ...baseOptions,
    ...(prefixParts.length > 0 ? { systemPromptPrefix: prefixParts.join('\n\n') } : {}),
    metadata,
  };
}
