import { safeJsonParse } from '../../shared/json';
import { collapseWhitespace, truncateText } from '../../shared/text';

export type AgentRole = 'user' | 'assistant' | 'system' | 'tool';

export interface ToolCallMessage {
  id: string;
  tool:
    | 'generate_driver_report'
    | 'generate_vehicle_report'
    | 'generate_unit_report'
    | 'generate_route_report'
    | 'generate_station_report'
    | 'generate_accident_investigation_report'
    | 'consult_omni'
    | 'consult_driver_expert'
    | 'consult_vehicle_expert'
    | 'consult_unit_expert'
    | 'consult_route_expert'
    | 'consult_station_expert'
    | 'consult_incident_expert'
    | 'rule_reply'
    | 'rule_asker'
    | 'rule_builder'
    | 'get_rule'
    | 'update_rule_draft'
    | 'get_rule_draft'
    | 'submit_rule_turn'
    | 'rule_exit'
    | 'request_further_info'
    | 'match_rules';
  args: Record<string, unknown>;
}

export interface ChatCompletionMessage {
  role: AgentRole;
  content: string;
  tool_call_id?: string;
  name?: string;
  tool_calls?: ToolCallMessage[];
}

export interface HistoryMessage {
  role: string;
  content: string;
}

export interface ContextHistoryBuildOptions {
  diagnosticsEnabled?: boolean;
  diagnosticsSource?: string;
}

export interface ContextDiagnosticsEnvLike {
  OPENAI_STREAM_DIAGNOSTICS?: string;
}

const INTERNAL_TOOL_PROTOCOL_MARKERS = [
  '请严格遵守以下规则',
  '必须使用上述命令格式',
  '如果需要调用工具',
  '如果不调用工具',
  '不要在回复中包含未调用的工具',
  '请在回复中使用以上命令调用工具',
  '使用以上命令调用工具',
  '不要直接调用API',
  '要调用的工具名称',
  '输入参数',
  '必须是以下之一',
  'must use the above command',
  'do not call api directly',
  'do not directly call api',
  'no need to implement code for these functions',
  'include the complete command',
  'api key or sensitive information',
] as const;

const STAGE_TEXT_PREFIXES = ['正在', '我正在', '我将', '将为', '马上', '准备', '开始'] as const;

export function buildContextFromHistory(
  historyMessages: HistoryMessage[],
  contextWindowMessages = 30,
  options: ContextHistoryBuildOptions = {}
): ChatCompletionMessage[] {
  const limitedMessages = historyMessages.slice(-contextWindowMessages);
  const messages: ChatCompletionMessage[] = [];

  for (const [limitedIndex, message] of limitedMessages.entries()) {
    if (message.role === 'system' || message.role === 'tool') {
      continue;
    }

    if (message.role !== 'user' && message.role !== 'assistant') {
      continue;
    }

    let content = String(message.content || '').trim();
    if (!content) {
      continue;
    }

    if (message.role === 'assistant') {
      const sanitized = sanitizeAssistantHistoryContent(content);
      if (sanitized.action !== 'kept') {
        emitContextHistoryDiagnostic(options, {
          action: sanitized.action,
          reason: sanitized.reason,
          role: message.role,
          limited_index: limitedIndex,
          original_chars: content.length,
          sanitized_chars: sanitized.content.length,
          original_preview: previewDiagnosticText(content),
          sanitized_preview: previewDiagnosticText(sanitized.content),
        });
      }
      content = sanitized.content;
      if (!content) {
        continue;
      }
    }

    messages.push({
      role: message.role,
      content: truncateText(content, 1200),
    });
  }

  return messages;
}

export function buildContextHistoryOptions(
  env: ContextDiagnosticsEnvLike | undefined,
  diagnosticsSource: string
): ContextHistoryBuildOptions {
  return {
    diagnosticsEnabled:
      String(env?.OPENAI_STREAM_DIAGNOSTICS ?? '').trim().toLowerCase() === 'true',
    diagnosticsSource,
  };
}

export function sanitizeAssistantHistoryContent(content: string): {
  action: 'kept' | 'trimmed' | 'dropped';
  content: string;
  reason?: string;
} {
  const trimmed = content.trim();
  const marker = findFirstInternalProtocolMarker(trimmed);
  if (!marker) {
    return { action: 'kept', content: trimmed };
  }

  const prefix = trimmed
    .slice(0, marker.index)
    .replace(/[#\s:：-]+$/g, '')
    .trim();

  if (!prefix || looksLikeAssistantStageText(prefix)) {
    return {
      action: 'dropped',
      content: '',
      reason: `internal_protocol_marker:${marker.marker}`,
    };
  }

  return {
    action: 'trimmed',
    content: prefix,
    reason: `internal_protocol_marker:${marker.marker}`,
  };
}

export function looksLikeInternalInstructionLeak(content: string): boolean {
  const normalized = collapseWhitespace(String(content || '')).toLowerCase();
  if (!normalized) {
    return false;
  }

  if (findFirstInternalProtocolMarker(normalized)) {
    return true;
  }

  const mentionsToolProtocol =
    normalized.includes('tool') ||
    normalized.includes('function') ||
    normalized.includes('schema') ||
    normalized.includes('工具') ||
    normalized.includes('函数') ||
    normalized.includes('命令');
  const mentionsExecutionDirective =
    normalized.includes('must') ||
    normalized.includes('do not') ||
    normalized.includes('api') ||
    normalized.includes('必须') ||
    normalized.includes('不要') ||
    normalized.includes('请确保') ||
    normalized.includes('直接调用');

  return mentionsToolProtocol && mentionsExecutionDirective;
}

export function formatContextMessage(
  row: { role: AgentRole; content: string },
  metadata: Record<string, unknown> | undefined,
  options: { toolOutputPreviewChars: number; messagePreviewChars: number }
): ChatCompletionMessage | null {
  let original = row.content ?? '';
  if (!original.trim()) {
    return null;
  }

  if (row.role === 'assistant') {
    const sanitized = sanitizeAssistantHistoryContent(original);
    if (sanitized.action === 'dropped') {
      return null;
    }
    original = sanitized.content;
  }

  const tool = metadata?.tool ? String(metadata.tool) : '';

  if (row.role === 'assistant' && tool) {
    if (
      tool === 'consult_omni' ||
      tool === 'consult_driver_expert' ||
      tool === 'consult_vehicle_expert' ||
      tool === 'consult_unit_expert' ||
      tool === 'consult_route_expert' ||
      tool === 'consult_station_expert' ||
      tool === 'consult_incident_expert'
    ) {
      return {
        role: 'assistant',
        content: truncateText(original, options.toolOutputPreviewChars),
      };
    }
    return {
      role: 'assistant',
      content: summarizeToolOutput(tool, original, options.toolOutputPreviewChars),
    };
  }

  return {
    role: row.role as 'user' | 'assistant',
    content: truncateText(original, options.messagePreviewChars),
  };
}

export function buildToolSummary(
  entries: Array<{ tool: string; args?: Record<string, unknown> }>,
  options: { toolSummaryLimit: number }
): string | null {
  if (!entries.length) return null;
  const recent = entries.slice(-options.toolSummaryLimit);
  const lines = recent.map((entry, index) => {
    const parts = [`#${index + 1}`, `tool=${entry.tool}`];
    const argsSummary = summarizeToolArgs(entry.tool, entry.args);
    if (argsSummary) {
      parts.push(`args=${argsSummary}`);
    }
    return parts.join(' ');
  });
  return `Recent tool calls:\n${lines.join('\n')}`;
}

function summarizeToolOutput(
  tool: string,
  content: string,
  toolOutputPreviewChars: number
): string {
  const summaryFromJson = extractSummaryFromJson(content);
  const previewSource = summaryFromJson || collapseWhitespace(content);
  const preview = truncateText(previewSource, toolOutputPreviewChars);
  if (!preview) {
    return '上一轮助手已生成工具结果摘要。';
  }
  return `上一轮助手基于工具结果生成的摘要：${preview}`;
}

function extractSummaryFromJson(content: string): string | null {
  const parsed = safeJsonParse(content);
  if (!parsed || typeof parsed !== 'object') {
    return null;
  }
  const record = parsed as Record<string, unknown>;
  const keys = ['summary', 'overview', 'note', 'conclusion'];
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function findFirstInternalProtocolMarker(content: string): { marker: string; index: number } | null {
  let first: { marker: string; index: number } | null = null;
  const searchable = content.toLowerCase();
  for (const marker of INTERNAL_TOOL_PROTOCOL_MARKERS) {
    const index = searchable.indexOf(marker.toLowerCase());
    if (index === -1) {
      continue;
    }
    if (!first || index < first.index) {
      first = { marker, index };
    }
  }
  return first;
}

function looksLikeAssistantStageText(content: string): boolean {
  const normalized = collapseWhitespace(content).replace(/[。.!！?？]+$/g, '').trim();
  if (!normalized) {
    return true;
  }
  if (normalized.length > 80) {
    return false;
  }
  return STAGE_TEXT_PREFIXES.some((prefix) => normalized.startsWith(prefix));
}

function previewDiagnosticText(content: string, limit = 180): string {
  return collapseWhitespace(content).slice(0, limit);
}

function emitContextHistoryDiagnostic(
  options: ContextHistoryBuildOptions,
  detail: Record<string, unknown>
): void {
  if (!options.diagnosticsEnabled) {
    return;
  }
  console.log(
    `[openai-stream-diagnostic] context-history-sanitize ${JSON.stringify({
      ts: new Date().toISOString(),
      source: options.diagnosticsSource ?? 'unknown',
      ...detail,
    })}`
  );
}

function summarizeToolArgs(tool: string, args?: Record<string, unknown>): string | null {
  if (!args) return null;
  if (tool === 'generate_driver_report') {
    return safeArgSummary(args.driver_name, 'driver');
  }
  if (tool === 'generate_vehicle_report') {
    return safeArgSummary(args.numberPlate, 'vehicle');
  }
  if (tool === 'generate_unit_report') {
    return safeArgSummary(args.organ_name, 'unit');
  }
  if (tool === 'generate_route_report') {
    return safeArgSummary(args.route_name, 'route');
  }
  if (tool === 'generate_station_report') {
    return safeArgSummary(args.station_name, 'station');
  }
  if (tool === 'generate_accident_investigation_report') {
    return safeArgSummary(args.driver_name, 'accident_driver');
  }
  if (tool === 'consult_omni') {
    return safeArgSummary(args.query, 'query');
  }
  if (
    tool === 'consult_driver_expert' ||
    tool === 'consult_vehicle_expert' ||
    tool === 'consult_unit_expert' ||
    tool === 'consult_route_expert' ||
    tool === 'consult_station_expert' ||
    tool === 'consult_incident_expert'
  ) {
    return safeArgSummary(args.query, 'query');
  }
  return safeArgSummary(JSON.stringify(args), 'args');
}

function safeArgSummary(value: unknown, label: string): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return `${label}:${truncateText(trimmed, 80)}`;
}
