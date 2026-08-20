import {
  parsePendingFurtherInfoState,
  type PendingFurtherInfoState,
} from '../chat/clarification-state';
import type {
  StructuredReportWorkerToolName,
  WorkerToolName,
} from '../chat/worker-runner';
import { safeJsonParse } from '../../shared/json';

interface D1PreparedStatementLike {
  bind: (...values: unknown[]) => D1PreparedStatementLike;
  first: <T = Record<string, unknown>>() => Promise<T | null>;
}

interface D1DatabaseLike {
  prepare: (query: string) => D1PreparedStatementLike;
}

export interface ReportFollowUpState {
  kind: 'structured_report_follow_up';
  source_tool: StructuredReportWorkerToolName;
}

export interface LatestAssistantRoutingContext {
  tool: WorkerToolName | null;
  assistantContent: string | null;
  reportFollowUp: ReportFollowUpState | null;
  pendingFurtherInfo: PendingFurtherInfoState | null;
  error: string | null;
}

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

function isStructuredReportWorkerToolName(
  value: unknown
): value is StructuredReportWorkerToolName {
  return (
    value === 'generate_driver_report' ||
    value === 'generate_vehicle_report' ||
    value === 'generate_unit_report' ||
    value === 'generate_route_report' ||
    value === 'generate_station_report' ||
    value === 'generate_accident_investigation_report'
  );
}

function parseReportFollowUpState(value: unknown): ReportFollowUpState | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;

  const record = value as Record<string, unknown>;
  if (record.kind !== 'structured_report_follow_up') return null;

  const sourceTool = record.source_tool;
  if (!isStructuredReportWorkerToolName(sourceTool)) return null;

  return {
    kind: 'structured_report_follow_up',
    source_tool: sourceTool,
  };
}

export async function getLatestAssistantRoutingContext(
  db: D1DatabaseLike,
  sessionId: string
): Promise<LatestAssistantRoutingContext | null> {
  const row = await db
    .prepare(
      'SELECT content, metadata FROM agent_messages WHERE session_id = ? AND role = ? ORDER BY created_at DESC LIMIT 1'
    )
    .bind(sessionId, 'assistant')
    .first<{ content: string | null; metadata: string | null }>();

  if (!row?.metadata) return null;

  const parsed = safeJsonParse(row.metadata);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;

  const record = parsed as Record<string, unknown>;
  const toolValue = record.tool;
  const tool = isWorkerToolName(toolValue) ? toolValue : null;

  return {
    tool,
    assistantContent: typeof row.content === 'string' ? row.content : null,
    reportFollowUp: parseReportFollowUpState(record.report_follow_up),
    pendingFurtherInfo: parsePendingFurtherInfoState(record.pending_further_info),
    error: typeof record.error === 'string' ? record.error : null,
  };
}

export function getLatestStructuredReportSource(
  context: LatestAssistantRoutingContext | null
): StructuredReportWorkerToolName | null {
  if (!context) return null;

  if (!context.error && context.tool && isStructuredReportWorkerToolName(context.tool)) {
    return context.tool;
  }
  if (
    (
      context.tool === 'consult_omni' ||
      context.tool === 'consult_driver_expert' ||
      context.tool === 'consult_vehicle_expert' ||
      context.tool === 'consult_unit_expert' ||
      context.tool === 'consult_route_expert' ||
      context.tool === 'consult_station_expert' ||
      context.tool === 'consult_incident_expert'
    ) &&
    context.reportFollowUp
  ) {
    return context.reportFollowUp.source_tool;
  }

  return null;
}

export function getLatestStructuredReportFailureSource(
  context: LatestAssistantRoutingContext | null
): StructuredReportWorkerToolName | null {
  if (!context?.error) return null;
  return context.tool && isStructuredReportWorkerToolName(context.tool)
    ? context.tool
    : null;
}
