import { jsonResponse, readJson } from '../../infra/http/response';

type WorkerExecutionContext = {
  waitUntil: (promise: Promise<unknown>) => void;
};

interface ChatHandlersDeps {
  request: Request;
  relativePath: string;
  env: { DB: unknown };
  auth: unknown;
  ctx?: WorkerExecutionContext;
  getAgentSession: any;
  getAgentSessionMeta: any;
  handleChatStream: any;
  handleDirectStreamProbe: any;
  handlePipelineStreamProbe: any;
  handleChat: any;
  handleReportSummary?: any;
}

function buildHistoryMessagesFromSession(
  session: { messages?: Array<{ role: string; content: string }> } | null
): Array<{ role: string; content: string }> {
  if (!session?.messages?.length) {
    return [];
  }

  return session.messages
    .filter((message) => message.role === 'user' || message.role === 'assistant')
    .map((message) => ({
      role: message.role,
      content: String(message.content || ''),
    }));
}

export async function handleChatApiRequest(deps: ChatHandlersDeps): Promise<Response | null> {
  const {
    request,
    relativePath,
    env,
    auth,
    ctx,
    getAgentSession,
    getAgentSessionMeta,
    handleChatStream,
    handleDirectStreamProbe,
    handlePipelineStreamProbe,
    handleChat,
    handleReportSummary,
  } = deps;

  if (
    (relativePath === '/reports/summary' || relativePath.startsWith('/reports/summary/')) &&
    request.method === 'POST'
  ) {
    if (!handleReportSummary) {
      return jsonResponse({ error: 'report summary handler unavailable' }, { status: 500 });
    }
    const pathReportType = relativePath.startsWith('/reports/summary/')
      ? relativePath.slice('/reports/summary/'.length).trim()
      : '';
    const payload = await readJson<{
      type?: string;
      reportType?: string;
      tool?: string;
      name?: string;
      id?: string;
      nameOrId?: string;
      entityId?: string;
      driverName?: string;
      driver_name?: string;
      accidentDate?: string;
      accident_date?: string;
      numberPlate?: string;
      organName?: string;
      organ_name?: string;
      routeName?: string;
      route_name?: string;
      stationName?: string;
      station_name?: string;
      busStationName?: string;
      ppartition?: string;
      partition?: string;
    }>(request);

    const reportRequest = resolveReportSummaryRequest(payload, pathReportType);
    if (!reportRequest.ok) {
      return jsonResponse({ error: reportRequest.error }, { status: 400 });
    }
    const accidentDate = String(payload?.accidentDate ?? payload?.accident_date ?? '').trim();
    if (reportRequest.type === 'accident' && !/^\d{14}$/.test(accidentDate)) {
      return jsonResponse(
        { error: 'missing or invalid accidentDate, expected yyyyMMddHHmmss' },
        { status: 400 }
      );
    }
    const reply = await handleReportSummary(env, {
      type: reportRequest.type,
      nameOrId: reportRequest.nameOrId,
      ppartition:
        reportRequest.type === 'accident'
          ? undefined
          : String(payload?.ppartition ?? payload?.partition ?? '').trim() || undefined,
      accidentDate:
        reportRequest.type === 'accident'
          ? accidentDate || undefined
          : undefined,
    });
    return jsonResponse(reply);
  }

  if (relativePath === '/chat/stream' && request.method === 'POST') {
    const payload = await readJson<{
      sessionId: string;
      content: string;
      messages?: Array<{ role: string; content: string }>;
    }>(request);
    if (!payload?.content) {
      return jsonResponse({ error: '缺少 content 参数' }, { status: 400 });
    }
    if (!payload?.sessionId) {
      return jsonResponse({ error: '缺少 sessionId 参数' }, { status: 400 });
    }
    const session = await getAgentSessionMeta(env.DB, payload.sessionId, auth);
    if (!session) {
      return jsonResponse({ error: 'session not found' }, { status: 404 });
    }
    const sessionDetail = await getAgentSession(env.DB, payload.sessionId, auth);
    return handleChatStream(
      env,
      payload.sessionId,
      payload.content,
      buildHistoryMessagesFromSession(sessionDetail),
      ctx
    );
  }

  if (relativePath === '/chat/direct-stream-probe' && request.method === 'POST') {
    const payload = await readJson<{ content?: string }>(request);
    const content = String(payload?.content ?? '').trim();
    if (!content) {
      return jsonResponse({ error: 'missing content' }, { status: 400 });
    }
    return handleDirectStreamProbe(env, content);
  }

  if (relativePath === '/chat/pipeline-stream-probe' && request.method === 'POST') {
    const payload = await readJson<{ content?: string; routerMode?: string }>(request);
    const content = String(payload?.content ?? '').trim();
    if (!content) {
      return jsonResponse({ error: 'missing content' }, { status: 400 });
    }
    const routerMode = payload?.routerMode === 'function' ? 'function' : 'command';
    return handlePipelineStreamProbe(env, content, { routerMode });
  }

  if (relativePath === '/chat' && request.method === 'POST') {
    const payload = await readJson<{
      sessionId: string;
      content: string;
      messages?: Array<{ role: string; content: string }>;
    }>(request);
    if (!payload?.content) {
      return jsonResponse({ error: '缺少 content 参数' }, { status: 400 });
    }
    if (!payload?.sessionId) {
      return jsonResponse({ error: '缺少 sessionId 参数' }, { status: 400 });
    }
    const session = await getAgentSessionMeta(env.DB, payload.sessionId, auth);
    if (!session) {
      return jsonResponse({ error: 'session not found' }, { status: 404 });
    }
    const sessionDetail = await getAgentSession(env.DB, payload.sessionId, auth);
    const reply = await handleChat(
      env,
      payload.sessionId,
      payload.content,
      buildHistoryMessagesFromSession(sessionDetail),
      ctx
    );
    return jsonResponse(reply);
  }

  return null;
}

type ReportSummaryType = 'driver' | 'vehicle' | 'unit' | 'route' | 'station' | 'accident';

function normalizeReportSummaryType(value: unknown): ReportSummaryType | null {
  const normalized = String(value ?? '').trim();
  if (!normalized) return null;
  if (normalized === 'driver' || normalized === 'generate_driver_report') return 'driver';
  if (
    normalized === 'vehicle' ||
    normalized === 'bus' ||
    normalized === 'generate_vehicle_report'
  ) {
    return 'vehicle';
  }
  if (normalized === 'unit' || normalized === 'company' || normalized === 'generate_unit_report') {
    return 'unit';
  }
  if (normalized === 'route' || normalized === 'line' || normalized === 'generate_route_report') {
    return 'route';
  }
  if (
    normalized === 'station' ||
    normalized === 'bus_station' ||
    normalized === 'generate_station_report'
  ) {
    return 'station';
  }
  if (
    normalized === 'accident' ||
    normalized === 'incident' ||
    normalized === 'generate_accident_investigation_report'
  ) {
    return 'accident';
  }
  return null;
}

function pickString(...values: unknown[]): string {
  for (const value of values) {
    const text = String(value ?? '').trim();
    if (text) return text;
  }
  return '';
}

function resolveReportSummaryRequest(
  payload:
    | {
        type?: string;
        reportType?: string;
        tool?: string;
        name?: string;
        id?: string;
        nameOrId?: string;
        entityId?: string;
        driverName?: string;
        driver_name?: string;
        accident_date?: string;
        numberPlate?: string;
        organName?: string;
        organ_name?: string;
        routeName?: string;
        route_name?: string;
        stationName?: string;
        station_name?: string;
        busStationName?: string;
      }
    | null
    | undefined,
  pathReportType: string
): { ok: true; type: ReportSummaryType; nameOrId: string } | { ok: false; error: string } {
  const explicitType =
    normalizeReportSummaryType(pathReportType) ??
    normalizeReportSummaryType(payload?.type) ??
    normalizeReportSummaryType(payload?.reportType) ??
    normalizeReportSummaryType(payload?.tool);
  const invalidExplicitType =
    pathReportType || payload?.type || payload?.reportType || payload?.tool;

  if (invalidExplicitType && !explicitType) {
    return {
      ok: false,
      error:
        'invalid report type, expected driver | vehicle | unit | route | station | accident or generate_*_report',
    };
  }

  const candidates = [
    { type: 'driver' as const, nameOrId: pickString(payload?.driverName, payload?.driver_name) },
    { type: 'vehicle' as const, nameOrId: pickString(payload?.numberPlate) },
    { type: 'unit' as const, nameOrId: pickString(payload?.organName, payload?.organ_name) },
    { type: 'route' as const, nameOrId: pickString(payload?.routeName, payload?.route_name) },
    {
      type: 'station' as const,
      nameOrId: pickString(payload?.stationName, payload?.station_name, payload?.busStationName),
    },
  ].filter((candidate) => candidate.nameOrId);

  if (explicitType) {
    const typedCandidate = candidates.find((candidate) => candidate.type === explicitType);
    const nameOrId =
      typedCandidate?.nameOrId ??
      (explicitType === 'accident' ? pickString(payload?.driverName, payload?.driver_name) : null) ??
      pickString(payload?.nameOrId, payload?.name, payload?.id, payload?.entityId);
    if (!nameOrId) {
      return { ok: false, error: `missing ${explicitType} report target parameter` };
    }
    return { ok: true, type: explicitType, nameOrId };
  }

  if (candidates.length === 1) {
    return { ok: true, type: candidates[0].type, nameOrId: candidates[0].nameOrId };
  }
  if (candidates.length > 1) {
    return {
      ok: false,
      error:
        'ambiguous report target parameters, pass only one of driverName | numberPlate | organName | routeName | stationName',
    };
  }

  return {
    ok: false,
    error:
      'missing report target parameter, expected one of driverName | numberPlate | organName | routeName | stationName',
  };
}
