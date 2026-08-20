import { isRecord } from '../../shared/guards';
import { safeJsonParse } from '../../shared/json';
import { encodeInternalWorkerToolCall } from './structured-lookup';
import type { WorkerToolCall, WorkerToolName } from './worker-runner';

export type PendingFurtherInfoOption = {
  label: string;
  value: string;
  aliases?: string[];
};

export type PendingFurtherInfoState = {
  kind: 'further_info';
  resume_tool: WorkerToolName;
  resume_mode: 'fill_args' | 'append_user_reply';
  missing_fields: string[];
  known_args: Record<string, unknown>;
  options: PendingFurtherInfoOption[];
  direct_resume: boolean;
};

type PendingFurtherInfoToolPayload = {
  pending_further_info: PendingFurtherInfoState;
};

const USER_FACING_MISSING_FIELD_MESSAGES: Record<string, string> = {
  driver_name: '请提供肇事驾驶员姓名。',
  accident_date: '请提供事故发生时间，格式 yyyyMMddHHmmss。',
  vehicle_id: '请提供要处理的车辆车牌号或车辆标识。',
  organ_name: '请提供要处理的单位名称。',
  route_name: '请提供要处理的线路名称或线路编号。',
  follow_up: '请补充你希望我继续处理的具体内容。',
  report_target_preference:
    '请先明确这次要生成哪一位对象的报告；如果你想做对比，也请说明是否需要分别生成多份报告后再对比。',
};

const AFFIRMATIVE_TOKENS = new Set([
  '是',
  '是的',
  '对',
  '对的',
  '没错',
  '确认',
  '确认是',
  '就是这个',
  '就这个',
  '可以',
  '好的',
  'yes',
  'ok',
]);

function isWorkerToolName(value: unknown): value is WorkerToolName {
  return (
    value === 'generate_driver_report' ||
    value === 'generate_vehicle_report' ||
    value === 'generate_unit_report' ||
    value === 'generate_route_report' ||
    value === 'generate_station_report' ||
    value === 'generate_accident_investigation_report' ||
    value === 'consult_omni' ||
    value === 'consult_driver_expert' ||
    value === 'consult_vehicle_expert' ||
    value === 'consult_unit_expert' ||
    value === 'consult_route_expert' ||
    value === 'consult_station_expert' ||
    value === 'consult_incident_expert' ||
    value === 'rule_reply' ||
    value === 'rule_asker' ||
    value === 'rule_builder'
  );
}

function normalizeArgToken(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/[\s"'`“”‘’《》〈〉「」『』【】\[\]{}()<>路,，。！？；:：\\|]+/g, '')
    .replace(/[-_]/g, '');
}

function cleanReplyValue(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '';

  const colonIndex = Math.max(trimmed.lastIndexOf(':'), trimmed.lastIndexOf('：'));
  const suffix = colonIndex >= 0 ? trimmed.slice(colonIndex + 1).trim() : '';
  if (suffix && suffix.length < trimmed.length) {
    return suffix;
  }

  return trimmed;
}

function looksLikeInternalFieldToken(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (USER_FACING_MISSING_FIELD_MESSAGES[trimmed]) return true;
  return /^[a-z][a-z0-9_]{1,63}$/i.test(trimmed);
}

function renderMissingFieldFallback(
  missingFields: string[],
  toolArgs?: Record<string, unknown>
): string | null {
  if (!missingFields.length) return null;

  const mappedMessages = missingFields
    .map((field) => USER_FACING_MISSING_FIELD_MESSAGES[field] ?? null)
    .filter((value): value is string => Boolean(value));

  if (mappedMessages.length > 0) {
    return mappedMessages.join('\n');
  }

  const options = Array.isArray(toolArgs?.options)
    ? (toolArgs.options as unknown[])
        .map((item) => {
          if (!isRecord(item)) return null;
          const label = String(item.label ?? '').trim();
          return label || null;
        })
        .filter((value): value is string => Boolean(value))
    : [];

  if (options.length > 0) {
    return `请先明确要选择哪一项：${options.slice(0, 5).join('、')}。`;
  }

  if (missingFields.some((field) => looksLikeInternalFieldToken(field))) {
    return '请补充继续处理当前任务所需的关键信息。';
  }

  if (missingFields.length === 1) {
    return missingFields[0];
  }

  return missingFields.join('\n');
}

function looksLikeFreshRequest(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (/[?？]/.test(trimmed)) return true;
  return /^(?:请|帮我|帮忙|查询|查下|查看|看看|生成|分析|统计|为什么|怎么|如何|what|why|how)\b/i.test(
    trimmed
  );
}

function normalizeOptions(value: unknown): PendingFurtherInfoOption[] {
  if (!Array.isArray(value)) return [];
  const result: PendingFurtherInfoOption[] = [];

  for (const item of value) {
    if (!isRecord(item)) continue;
    const label = String(item.label ?? '').trim();
    const valueToken = String(item.value ?? '').trim();
    if (!label || !valueToken) continue;

    const aliases = Array.isArray(item.aliases)
      ? item.aliases.map((alias) => String(alias ?? '').trim()).filter((alias) => alias.length > 0)
      : [];

    result.push({ label, value: valueToken, ...(aliases.length ? { aliases } : {}) });
  }

  return result;
}

function normalizeMissingFields(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item ?? '').trim()).filter((item) => item.length > 0);
}

function defaultResumeMode(tool: WorkerToolName): PendingFurtherInfoState['resume_mode'] {
  if (
    tool === 'generate_driver_report' ||
    tool === 'generate_vehicle_report' ||
    tool === 'generate_unit_report' ||
    tool === 'generate_route_report' ||
    tool === 'generate_station_report' ||
    tool === 'generate_accident_investigation_report'
  ) {
    return 'fill_args';
  }
  return 'append_user_reply';
}

export function parsePendingFurtherInfoState(value: unknown): PendingFurtherInfoState | null {
  if (!isRecord(value)) return null;
  if (value.kind !== 'further_info') return null;

  const resumeTool = value.resume_tool;
  if (!isWorkerToolName(resumeTool)) return null;

  const resumeMode =
    value.resume_mode === 'fill_args' || value.resume_mode === 'append_user_reply'
      ? value.resume_mode
      : defaultResumeMode(resumeTool);

  const missingFields = normalizeMissingFields(value.missing_fields);
  const knownArgs = isRecord(value.known_args) ? value.known_args : {};
  const options = normalizeOptions(value.options);
  const directResume = typeof value.direct_resume === 'boolean' ? value.direct_resume : true;

  return {
    kind: 'further_info',
    resume_tool: resumeTool,
    resume_mode: resumeMode,
    missing_fields: missingFields,
    known_args: knownArgs,
    options,
    direct_resume: directResume,
  };
}

export function createPendingFurtherInfoState(input: {
  resume_tool: WorkerToolName;
  resume_mode?: PendingFurtherInfoState['resume_mode'];
  missing_fields?: string[];
  known_args?: Record<string, unknown>;
  options?: PendingFurtherInfoOption[];
  direct_resume?: boolean;
}): PendingFurtherInfoState {
  return {
    kind: 'further_info',
    resume_tool: input.resume_tool,
    resume_mode: input.resume_mode ?? defaultResumeMode(input.resume_tool),
    missing_fields: [...(input.missing_fields ?? [])].filter((item) => item.trim().length > 0),
    known_args: input.known_args ?? {},
    options: [...(input.options ?? [])],
    direct_resume: input.direct_resume ?? true,
  };
}

export function buildPendingFurtherInfoToolPayload(
  args: Record<string, unknown>
): PendingFurtherInfoToolPayload | null {
  const resumeTool = args.resume_tool;

  if (!isWorkerToolName(resumeTool)) {
    return null;
  }

  const pending = parsePendingFurtherInfoState({
    kind: 'further_info',
    resume_tool: resumeTool,
    resume_mode: args.resume_mode,
    missing_fields: args.missing_fields,
    known_args: args.known_args,
    options: args.options,
    direct_resume: args.direct_resume,
  });

  if (!pending) return null;

  return {
    pending_further_info: pending,
  };
}

export function resolveFurtherInfoDisplayMessage(
  assistantContent: string | null | undefined,
  toolArgs?: Record<string, unknown>
): string {
  const content = String(assistantContent ?? '').trim();
  if (content && !looksLikeInternalFieldToken(content)) {
    return content;
  }

  const legacyAssistantMessage = String(toolArgs?.assistant_message ?? '').trim();
  if (legacyAssistantMessage) {
    return legacyAssistantMessage;
  }

  const missingFields = Array.isArray(toolArgs?.missing_fields)
    ? (toolArgs?.missing_fields as unknown[])
        .map((item) => String(item ?? '').trim())
        .filter((item) => item.length > 0)
    : [];
  const fallbackFromMissingFields = renderMissingFieldFallback(missingFields, toolArgs);
  if (fallbackFromMissingFields) {
    return fallbackFromMissingFields;
  }

  return '请提供完成当前任务所需的补充信息。';
}

function parseOptionByReply(
  options: PendingFurtherInfoOption[],
  userContent: string
): PendingFurtherInfoOption | null {
  if (!options.length) return null;

  const trimmed = userContent.trim();
  const normalized = normalizeArgToken(trimmed);
  if (!normalized) return null;

  const indexMatch = normalized.match(/^(?:第)?([123456789一二三四五六七八九])(?:个|条|项)?$/u);
  if (indexMatch) {
    const indexMap: Record<string, number> = {
      '1': 0,
      '2': 1,
      '3': 2,
      '4': 3,
      '5': 4,
      '6': 5,
      '7': 6,
      '8': 7,
      '9': 8,
      一: 0,
      二: 1,
      三: 2,
      四: 3,
      五: 4,
      六: 5,
      七: 6,
      八: 7,
      九: 8,
    };
    const index = indexMap[indexMatch[1]];
    if (index != null) {
      return options[index] ?? null;
    }
  }

  if (options.length === 1 && AFFIRMATIVE_TOKENS.has(normalized)) {
    return options[0];
  }

  return (
    options.find((option) => {
      const tokens = [option.label, option.value, ...(option.aliases ?? [])];
      return tokens.some((token) => normalizeArgToken(token) === normalized);
    }) ?? null
  );
}

function buildAppendReplyArgs(
  state: PendingFurtherInfoState,
  userReply: string
): Record<string, unknown> | null {
  const args = { ...state.known_args };
  const argKey =
    state.resume_tool === 'consult_omni' ||
    state.resume_tool === 'consult_driver_expert' ||
    state.resume_tool === 'consult_vehicle_expert' ||
    state.resume_tool === 'consult_unit_expert' ||
    state.resume_tool === 'consult_route_expert' ||
    state.resume_tool === 'consult_station_expert' ||
    state.resume_tool === 'consult_incident_expert'
      ? 'query'
      : 'user_query';
  const base = String(args[argKey] ?? '').trim();
  const reply = userReply.trim();
  if (!reply) return null;
  args[argKey] = base ? `${base}\n补充信息：${reply}` : reply;
  return args;
}

function buildFillArgs(
  state: PendingFurtherInfoState,
  userReply: string
): Record<string, unknown> | null {
  if (!state.missing_fields.length) return null;
  if (state.missing_fields.length > 1) return null;

  const option = parseOptionByReply(state.options, userReply);
  const value = option?.value ?? cleanReplyValue(userReply);
  if (!value) return null;

  return {
    ...state.known_args,
    [state.missing_fields[0]]: value,
  };
}

function buildResumeToolCall(
  state: PendingFurtherInfoState,
  userReply: string
): WorkerToolCall | null {
  const args =
    state.resume_mode === 'append_user_reply'
      ? buildAppendReplyArgs(state, userReply)
      : buildFillArgs(state, userReply);
  if (!args) return null;
  return { tool: state.resume_tool, args };
}

async function getPendingFurtherInfoState(
  db: any,
  sessionId: string
): Promise<PendingFurtherInfoState | null> {
  const row: { metadata: string | null } | null = await db
    .prepare(
      'SELECT metadata FROM agent_messages WHERE session_id = ? AND role = ? ORDER BY created_at DESC LIMIT 1'
    )
    .bind(sessionId, 'assistant')
    .first();
  if (!row?.metadata) return null;
  const parsed = safeJsonParse(row.metadata);
  if (!isRecord(parsed)) return null;
  return parsePendingFurtherInfoState(parsed.pending_further_info);
}

export async function rewritePendingFurtherInfoFollowUp(
  db: any,
  sessionId: string,
  userContent: string
): Promise<string | null> {
  const state = await getPendingFurtherInfoState(db, sessionId);
  if (!state?.direct_resume) return null;

  const trimmed = userContent.trim();
  if (!trimmed) return null;
  if (looksLikeFreshRequest(trimmed)) return null;

  const toolCall = buildResumeToolCall(state, trimmed);
  if (!toolCall) return null;
  return encodeInternalWorkerToolCall(toolCall);
}
