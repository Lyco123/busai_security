import { processOpenAIStream } from '../../infra/llm/stream';
import { createSseWriter, sseResponse } from '../../infra/http/sse';
import { formatAgentError } from '../../shared/errors';
import { chunkText } from '../../shared/text';
import type { HistoryMessage } from './context';
import type { RouteRequestOptions } from './router-service';
import type { ChatTurnContext, ChatTurnMetadataDetails } from './turn-context';
import { DEFAULT_RULE_ROUTING_MODE } from './turn-context';
import { formatStructuredOutput, type OutputFormatterEnv } from './output-formatter';
import { encodeInternalWorkerToolCall, type StructuredLookupToolName } from './structured-lookup';
import {
  createSessionRunRepository,
  type SessionRunMode,
  type SessionRunRecord,
} from './session-run-repository';

type WorkerExecutionContext = {
  waitUntil: (promise: Promise<unknown>) => void;
};

function logChatStreamStage(
  env: any,
  stage: string,
  detail: Record<string, unknown> = {}
): void {
  if (String(env?.OPENAI_STREAM_DIAGNOSTICS ?? '').trim().toLowerCase() !== 'true') {
    return;
  }
  console.log(
    `[chat-stream-stage] ${stage} ${JSON.stringify({
      ts: new Date().toISOString(),
      ...detail,
    })}`
  );
}

function buildReportEnvOverride(env: any): any | undefined {
  const reportBaseUrl = (env.OPENAI_REPORT_URL ?? env.OPENAI_REPORT_BASE_URL ?? '').trim();
  const selfHostedReportBaseUrl = (env.OPENAI_LOCAL_REPORT_BASE_URL ?? '').trim();
  const selfHostedReportModel = (env.OPENAI_LOCAL_REPORT_MODEL ?? '').trim();
  if (!reportBaseUrl && !selfHostedReportBaseUrl) return undefined;
  const reportApiKey = (env.OPENAI_REPORT_API_KEY ?? '').trim();
  return {
    ...env,
    OPENAI_BASE_URL: reportBaseUrl || env.OPENAI_BASE_URL,
    OPENAI_API_KEY: reportApiKey || env.OPENAI_API_KEY,
    OPENAI_WORKER_MODEL: env.OPENAI_REPORT_MODEL || env.OPENAI_MODEL,
    OPENAI_LOCAL_BASE_URL: selfHostedReportBaseUrl || undefined,
    OPENAI_LOCAL_MODEL: selfHostedReportModel || undefined,
  };
}

interface AgentMessage {
  id: string;
  role: 'assistant';
  content: string;
  createdAt: string;
  status?: 'complete' | 'error';
  sources?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
  tools?: unknown[];
}

interface ChatReply {
  role: 'assistant';
  content: string;
  sources?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
  tools?: unknown[];
}

type ReportSummaryType = 'driver' | 'vehicle' | 'unit' | 'route' | 'station' | 'accident';

interface ReportSummaryPayload {
  type: ReportSummaryType;
  nameOrId: string;
  ppartition?: string;
  accidentDate?: string;
}

interface ChatServiceDeps {
  TOOL_OUTPUT_PREVIEW_CHARS: number;
  createId: (prefix: string) => string;
  getHistoryMessages: (db: any, sessionId: string) => Promise<HistoryMessage[]>;
  saveMessage: (
    db: any,
    sessionId: string,
    message: {
      id: string;
      role: 'user' | 'assistant';
      content: string;
      status?: 'complete' | 'error';
      sources?: Array<Record<string, unknown>>;
      metadata?: Record<string, unknown>;
    }
  ) => Promise<void>;
  updateSessionPreview: (db: any, sessionId: string, preview: string) => Promise<void>;
  createTurnContext: (db: any, sessionId: string) => Promise<ChatTurnContext>;
  tryHandleRuleConfig: (
    env: any,
    sessionId: string,
    content: string,
    isStream: boolean,
    historyMessages: HistoryMessage[]
  ) => Promise<{
    content: string | ReadableStream;
    metadata?: Record<string, unknown>;
    sources?: Array<Record<string, unknown>>;
    leadingContent?: string;
    trailingContent?: string;
  } | null>;
  routeRequest: (
    env: any,
    content: string,
    historyMessages: HistoryMessage[],
    options: RouteRequestOptions
  ) => Promise<{
    content: string | ReadableStream;
    metadata?: Record<string, unknown>;
    sources?: Array<Record<string, unknown>>;
    leadingContent?: string;
    trailingContent?: string;
  }>;
  generatePreRouterOpening: (
    env: any,
    content: string,
    historyMessages?: HistoryMessage[],
    options?: Pick<RouteRequestOptions, 'onAssistantDelta' | 'onProbeEvent'>
  ) => Promise<{ content: string; emittedAt: string | null }>;
  decorateAssistantMetadata: (
    turnContext: ChatTurnContext,
    metadata: Record<string, unknown> | undefined,
    details?: ChatTurnMetadataDetails
  ) => Record<string, unknown>;
  hasDecoratedAssistantMetadata: (metadata: unknown) => boolean;
  maybeGenerateSessionTitle: (env: any, sessionId: string) => Promise<void>;
  scheduleSessionTitleGeneration: (
    ctx: WorkerExecutionContext | undefined,
    promise: Promise<void>
  ) => void;
  openDirectProbeStream: (env: any, content: string) => Promise<ReadableStream>;
}

export function createChatService(deps: ChatServiceDeps) {
  const sessionRunRepository = createSessionRunRepository();
  const RUN_LEASE_MS = 2 * 60 * 1000;
  const RUN_STALE_RUNNING_MS = 2 * 60 * 1000;
  const RUN_ACQUIRE_TIMEOUT_MS = 12 * 1000;
  const RUN_ACQUIRE_POLL_MS = 1000;

  async function handleChat(
    env: any,
    sessionId: string,
    content: string,
    _historyMessages: HistoryMessage[] = [],
    ctx?: WorkerExecutionContext
  ): Promise<ChatReply> {
    const run = await createQueuedRun(env, sessionId, content, 'chat');
    const acquiredRun = await waitForRunStart(env, run.id);
    if (!acquiredRun) {
      const latestRun = await sessionRunRepository.getRun(env.DB, run.id);
      return buildInactiveRunReply(latestRun ?? run);
    }

    try {
      const historyMessages = await deps.getHistoryMessages(env.DB, sessionId);
      const reply = await executeChatTurn(env, sessionId, content, historyMessages, ctx, run.id);
      await sessionRunRepository.completeRun(
        env.DB,
        run.id,
        reply as unknown as Record<string, unknown>
      );
      return reply;
    } catch (error) {
      await sessionRunRepository.failRun(env.DB, run.id, formatAgentError(error));
      throw error;
    }
  }

  async function executeChatTurn(
    env: any,
    sessionId: string,
    content: string,
    historyMessages: HistoryMessage[] = [],
    ctx?: WorkerExecutionContext,
    runId?: string
  ): Promise<ChatReply> {
    const userMessageId = deps.createId('msg');
    await deps.saveMessage(env.DB, sessionId, {
      id: userMessageId,
      role: 'user',
      content,
      status: 'complete',
    });

    const preview = content.slice(0, deps.TOOL_OUTPUT_PREVIEW_CHARS);
    await deps.updateSessionPreview(env.DB, sessionId, preview);

    const turnContext = await deps.createTurnContext(env.DB, sessionId);

    let assistantContent: string;
    let assistantLeadingContent = '';
    let assistantBaseContent = '';
    let assistantTrailingContent = '';
    let sources: Array<Record<string, unknown>> | undefined;
    let metadata: Record<string, unknown> | undefined;
    let preRouterOpeningEmittedAt: string | null = null;

    try {
      const preRouterOpening = await deps.generatePreRouterOpening(env, content, historyMessages);
      const preRouterOpeningContent = preRouterOpening.content;
      preRouterOpeningEmittedAt = preRouterOpening.emittedAt;

      const ruleConfigResult = await deps.tryHandleRuleConfig(
        env,
        sessionId,
        content,
        false,
        historyMessages
      );
      if (ruleConfigResult) {
        const baseContent =
          typeof ruleConfigResult.content === 'string' ? ruleConfigResult.content : '';
        assistantLeadingContent = `${preRouterOpeningContent}${ruleConfigResult.leadingContent ?? ''}`;
        assistantBaseContent = baseContent;
        assistantTrailingContent = ruleConfigResult.trailingContent ?? '';
        assistantContent = `${assistantLeadingContent}${assistantBaseContent}${assistantTrailingContent}`;
        metadata = deps.decorateAssistantMetadata(turnContext, ruleConfigResult.metadata, {
          selectedTool:
            typeof ruleConfigResult.metadata?.tool === 'string'
              ? String(ruleConfigResult.metadata.tool)
              : null,
        });
      } else {
        const routerResult = await deps.routeRequest(env, content, historyMessages, {
          sessionId,
          turnContext,
          suppressOpeningText: true,
        });
        const baseContent = typeof routerResult.content === 'string' ? routerResult.content : '';
        assistantLeadingContent = `${preRouterOpeningContent}${routerResult.leadingContent ?? ''}`;
        assistantBaseContent = baseContent;
        assistantTrailingContent = routerResult.trailingContent ?? '';
        assistantContent = `${assistantLeadingContent}${assistantBaseContent}${assistantTrailingContent}`;
        sources = routerResult.sources;
        metadata = routerResult.metadata;
      }
    } catch (error) {
      assistantLeadingContent = '';
      assistantBaseContent = formatAgentError(error);
      assistantTrailingContent = '';
      assistantContent = assistantBaseContent;
      metadata = deps.decorateAssistantMetadata(turnContext, metadata, {
        selectedTool: null,
      });
    }

    if (!deps.hasDecoratedAssistantMetadata(metadata)) {
      metadata = deps.decorateAssistantMetadata(turnContext, metadata, {
        selectedTool: typeof metadata?.tool === 'string' ? String(metadata.tool) : null,
      });
    }
    if (preRouterOpeningEmittedAt) {
      metadata = {
        ...(metadata ?? {}),
        opening_emitted_at: preRouterOpeningEmittedAt,
        opening_stage: 'pre_router',
      };
    }

    const formattedBaseContent = formatStructuredOutput(
      assistantBaseContent,
      metadata,
      env as OutputFormatterEnv
    );
    assistantContent = `${assistantLeadingContent}${formattedBaseContent}${assistantTrailingContent}`;

    if (runId && !(await sessionRunRepository.isRunRunning(env.DB, runId))) {
      return {
        role: 'assistant',
        content: assistantContent,
        sources,
        metadata,
        tools: Array.isArray(metadata?.tools) ? (metadata.tools as unknown[]) : [],
      };
    }

    const assistantMessageId = deps.createId('msg');
    await deps.saveMessage(env.DB, sessionId, {
      id: assistantMessageId,
      role: 'assistant',
      content: assistantContent,
      status: 'complete',
      sources,
      metadata,
    });

    const assistantPreview = assistantContent.slice(0, deps.TOOL_OUTPUT_PREVIEW_CHARS);
    await deps.updateSessionPreview(env.DB, sessionId, assistantPreview);

    deps.scheduleSessionTitleGeneration(ctx, deps.maybeGenerateSessionTitle(env, sessionId));

    return {
      role: 'assistant',
      content: assistantContent,
      sources,
      metadata,
      tools: Array.isArray(metadata?.tools) ? (metadata.tools as unknown[]) : [],
    };
  }

  async function handleChatStream(
    env: any,
    sessionId: string,
    content: string,
    _historyMessages: HistoryMessage[] = [],
    ctx?: WorkerExecutionContext
  ): Promise<Response> {
    const run = await createQueuedRun(env, sessionId, content, 'stream');
    logChatStreamStage(env, 'queued', {
      run_id: run.id,
      session_id: sessionId,
      content_chars: content.length,
    });

    const stream = new ReadableStream({
      async start(controller) {
        const sse = createSseWriter(controller);
        let runStarted = false;
        let turnContext: ChatTurnContext | null = null;
        let assistantContent = '';
        let sources: Array<Record<string, unknown>> | undefined;
        let metadata: Record<string, unknown> | undefined;
        let finalSent = false;

        try {
          logChatStreamStage(env, 'wait_run_start_started', {
            run_id: run.id,
            session_id: sessionId,
          });
          const acquiredRun = await waitForRunStart(env, run.id);
          logChatStreamStage(env, 'wait_run_start_done', {
            run_id: run.id,
            acquired: Boolean(acquiredRun),
          });
          if (!acquiredRun) {
            const latestRun = await sessionRunRepository.getRun(env.DB, run.id);
            sendInactiveRunStream(sse, latestRun ?? run);
            return;
          }
          runStarted = true;

          logChatStreamStage(env, 'history_fetch_started', { run_id: run.id });
          const historyMessages = await deps.getHistoryMessages(env.DB, sessionId);
          logChatStreamStage(env, 'history_fetch_done', {
            run_id: run.id,
            history_count: historyMessages.length,
            history_chars: historyMessages.reduce(
              (sum, message) => sum + String(message.content ?? '').length,
              0
            ),
          });
          const userMessageId = deps.createId('msg');
          logChatStreamStage(env, 'save_user_started', { run_id: run.id });
          await deps.saveMessage(env.DB, sessionId, {
            id: userMessageId,
            role: 'user',
            content,
            status: 'complete',
          });
          logChatStreamStage(env, 'save_user_done', { run_id: run.id });

          const preview = content.slice(0, deps.TOOL_OUTPUT_PREVIEW_CHARS);
          logChatStreamStage(env, 'update_preview_started', { run_id: run.id });
          await deps.updateSessionPreview(env.DB, sessionId, preview);
          logChatStreamStage(env, 'update_preview_done', { run_id: run.id });

          logChatStreamStage(env, 'turn_context_started', { run_id: run.id });
          turnContext = await deps.createTurnContext(env.DB, sessionId);
          logChatStreamStage(env, 'turn_context_done', { run_id: run.id });

          let preRouterOpeningEmittedAt: string | null = null;

          const appendAssistantDelta = (delta: string) => {
            if (!delta) return;
            assistantContent += delta;
            sse.send({ type: 'delta', run_id: run.id, delta });
          };
          const appendAssistantProgress: NonNullable<RouteRequestOptions['onAssistantProgress']> = (
            progress
          ) => {
            if (!progress?.text) return;
            sse.send({
              type: 'progress',
              run_id: run.id,
              code: progress.code,
              text: progress.text,
            });
          };
          const appendAgentEvent: NonNullable<RouteRequestOptions['onAgentEvent']> = (event) => {
            sse.send({
              ...event,
              run_id: run.id,
            });
          };

          sse.send({ type: 'start', run_id: run.id });
          logChatStreamStage(env, 'pre_router_opening_started', { run_id: run.id });
          const preRouterOpening = await deps.generatePreRouterOpening(
            env,
            content,
            historyMessages,
            {
              onAssistantDelta: appendAssistantDelta,
            }
          );
          preRouterOpeningEmittedAt = preRouterOpening.emittedAt;
          logChatStreamStage(env, 'pre_router_opening_done', {
            run_id: run.id,
            emitted: Boolean(preRouterOpeningEmittedAt),
          });

          logChatStreamStage(env, 'rule_config_started', { run_id: run.id });
          const ruleConfigResult = await deps.tryHandleRuleConfig(
            env,
            sessionId,
            content,
            true,
            historyMessages
          );
          logChatStreamStage(env, 'rule_config_done', {
            run_id: run.id,
            matched: Boolean(ruleConfigResult),
          });
          let routerResult = ruleConfigResult;
          if (!routerResult) {
            logChatStreamStage(env, 'route_request_started', { run_id: run.id });
            routerResult = await deps.routeRequest(env, content, historyMessages, {
              isStream: true,
              sessionId,
              turnContext,
              onAssistantDelta: appendAssistantDelta,
              onAssistantProgress: appendAssistantProgress,
              onAgentEvent: appendAgentEvent,
              suppressOpeningText: true,
            });
            logChatStreamStage(env, 'route_request_done', {
              run_id: run.id,
              content_type: routerResult.content instanceof ReadableStream ? 'stream' : 'buffer',
              tool: routerResult.metadata?.tool ?? null,
            });
          } else {
            routerResult = {
              ...routerResult,
              metadata: deps.decorateAssistantMetadata(turnContext, routerResult.metadata, {
                selectedTool:
                  typeof routerResult.metadata?.tool === 'string'
                    ? String(routerResult.metadata.tool)
                    : null,
              }),
            };
          }

          metadata = routerResult.metadata;
          if (preRouterOpeningEmittedAt) {
            metadata = {
              ...(metadata ?? {}),
              opening_emitted_at: preRouterOpeningEmittedAt,
              opening_stage: 'pre_router',
            };
          }
          sources = routerResult.sources;

          if (routerResult.content instanceof ReadableStream) {
            logChatStreamStage(env, 'model_stream_started', { run_id: run.id });
            await processOpenAIStream(routerResult.content, appendAssistantDelta);
            logChatStreamStage(env, 'model_stream_done', {
              run_id: run.id,
              assistant_chars: assistantContent.length,
            });
            if (routerResult.trailingContent) {
              appendAssistantDelta(routerResult.trailingContent);
            }
          } else {
            const mainContent = String(routerResult.content);
            const isToolOutput =
              Boolean(metadata?.tool) &&
              metadata?.tool !== 'consult_omni' &&
              metadata?.tool !== 'consult_driver_expert' &&
              metadata?.tool !== 'consult_vehicle_expert' &&
              metadata?.tool !== 'consult_unit_expert' &&
              metadata?.tool !== 'consult_route_expert' &&
              metadata?.tool !== 'consult_incident_expert';

            logChatStreamStage(env, 'format_output_started', {
              run_id: run.id,
              main_content_chars: mainContent.length,
              tool: metadata?.tool ?? null,
            });
            const formattedContent = formatStructuredOutput(
              mainContent,
              metadata,
              env as OutputFormatterEnv
            );
            logChatStreamStage(env, 'format_output_done', {
              run_id: run.id,
              formatted_chars: formattedContent.length,
            });

            if (!isToolOutput) {
              logChatStreamStage(env, 'buffered_delta_started', { run_id: run.id });
              for (const chunk of chunkText(formattedContent)) {
                appendAssistantDelta(chunk);
              }
              logChatStreamStage(env, 'buffered_delta_done', { run_id: run.id });
            } else {
              appendAssistantDelta(formattedContent);
            }
            if (routerResult.trailingContent) {
              appendAssistantDelta(routerResult.trailingContent);
            }
          }

          logChatStreamStage(env, 'metadata_decorate_started', { run_id: run.id });
          if (!deps.hasDecoratedAssistantMetadata(metadata)) {
            metadata = deps.decorateAssistantMetadata(turnContext, metadata, {
              selectedTool: typeof metadata?.tool === 'string' ? String(metadata.tool) : null,
            });
          }
          logChatStreamStage(env, 'metadata_decorate_done', { run_id: run.id });

          logChatStreamStage(env, 'run_active_check_started', { run_id: run.id });
          if (!(await sessionRunRepository.isRunRunning(env.DB, run.id))) {
            throw new Error('Session run is no longer active.');
          }
          logChatStreamStage(env, 'run_active_check_done', { run_id: run.id });

          const finalMessage: AgentMessage = {
            id: deps.createId('msg'),
            role: 'assistant',
            content: assistantContent,
            createdAt: new Date().toISOString(),
            status: 'complete',
            sources,
            metadata,
            tools: Array.isArray(metadata?.tools) ? (metadata.tools as unknown[]) : [],
          };

          logChatStreamStage(env, 'save_assistant_started', {
            run_id: run.id,
            assistant_chars: assistantContent.length,
          });
          await deps.saveMessage(env.DB, sessionId, {
            id: finalMessage.id,
            role: finalMessage.role,
            content: finalMessage.content,
            status: finalMessage.status,
            sources: finalMessage.sources,
            metadata: finalMessage.metadata,
          });
          logChatStreamStage(env, 'save_assistant_done', { run_id: run.id });

          const assistantPreview = assistantContent.slice(0, deps.TOOL_OUTPUT_PREVIEW_CHARS);
          logChatStreamStage(env, 'update_assistant_preview_started', { run_id: run.id });
          await deps.updateSessionPreview(env.DB, sessionId, assistantPreview);
          logChatStreamStage(env, 'update_assistant_preview_done', { run_id: run.id });

          deps.scheduleSessionTitleGeneration(ctx, deps.maybeGenerateSessionTitle(env, sessionId));

          logChatStreamStage(env, 'complete_run_started', { run_id: run.id });
          await sessionRunRepository.completeRun(
            env.DB,
            run.id,
            finalMessage as unknown as Record<string, unknown>
          );
          logChatStreamStage(env, 'complete_run_done', { run_id: run.id });

          sse.send({ type: 'final', run_id: run.id, message: finalMessage });
          logChatStreamStage(env, 'final_sent', { run_id: run.id });
          finalSent = true;
        } catch (error) {
          const errorMessage = formatAgentError(error);
          logChatStreamStage(env, 'stream_failed', {
            run_id: run.id,
            error: errorMessage,
            assistant_chars: assistantContent.length,
          });
          const fallbackContent = buildStreamFallbackContent(assistantContent, errorMessage);
          const errorMetadata = turnContext
            ? deps.decorateAssistantMetadata(turnContext, metadata, { selectedTool: null })
            : {
                ...(metadata ?? {}),
                session_run_id: run.id,
              };
          const fallbackMessage: AgentMessage = {
            id: deps.createId('msg'),
            role: 'assistant',
            content: fallbackContent,
            createdAt: new Date().toISOString(),
            status: 'error',
            sources,
            metadata: {
              ...(errorMetadata ?? {}),
              stream_error: errorMessage,
              session_run_id: run.id,
            },
            tools: Array.isArray(metadata?.tools) ? (metadata.tools as unknown[]) : [],
          };

          if (runStarted) {
            await deps.saveMessage(env.DB, sessionId, {
              id: fallbackMessage.id,
              role: fallbackMessage.role,
              content: fallbackMessage.content,
              status: fallbackMessage.status,
              sources: fallbackMessage.sources,
              metadata: fallbackMessage.metadata,
            });
            await deps.updateSessionPreview(
              env.DB,
              sessionId,
              fallbackMessage.content.slice(0, deps.TOOL_OUTPUT_PREVIEW_CHARS)
            );
          }
          await sessionRunRepository.failRun(env.DB, run.id, errorMessage);
          if (!finalSent) {
            if (!assistantContent) {
              sse.send({ type: 'delta', run_id: run.id, delta: fallbackMessage.content });
            }
            sse.send({ type: 'final', run_id: run.id, message: fallbackMessage });
            finalSent = true;
          }
        } finally {
          sse.done();
          controller.close();
        }
      },
    });

    return sseResponse(stream);
  }

  async function handleDirectStreamProbe(env: any, content: string): Promise<Response> {
    const stream = await deps.openDirectProbeStream(env, content);
    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  }

  async function handlePipelineStreamProbe(
    env: any,
    content: string,
    options: { routerMode?: 'command' | 'function' } = {}
  ): Promise<Response> {
    const stream = new ReadableStream({
      async start(controller) {
        const sse = createSseWriter(controller);
        const turnContext: ChatTurnContext = {
          routingMode: DEFAULT_RULE_ROUTING_MODE,
          variantContext: null,
        };
        let streamedContent = '';

        const appendAssistantDelta = (delta: string) => {
          if (!delta) return;
          streamedContent += delta;
          sse.send({ type: 'delta', delta });
        };
        const emitProbeStage = (stage: string, detail?: Record<string, unknown>) => {
          sse.send({
            type: 'probe_stage',
            stage,
            ...(detail ? { detail } : {}),
          });
        };

        try {
          sse.send({ type: 'start' });
          emitProbeStage('pipeline_started');
          emitProbeStage('pre_router_opening_started');
          const preRouterOpening = await deps.generatePreRouterOpening(env, content, [], {
            onAssistantDelta: appendAssistantDelta,
            onProbeEvent(event) {
              sse.send(event);
            },
          });
          emitProbeStage(
            preRouterOpening.emittedAt ? 'pre_router_opening_emitted' : 'pre_router_opening_skipped'
          );
          emitProbeStage('route_request_started');
          const routerResult = await deps.routeRequest(env, content, [], {
            isStream: true,
            turnContext,
            useCommandRouter: options.routerMode !== 'function',
            onAssistantDelta: appendAssistantDelta,
            onAssistantProgress(progress) {
              if (!progress?.text) return;
              sse.send({ type: 'progress', code: progress.code, text: progress.text });
            },
            onAgentEvent(event) {
              sse.send(event);
            },
            onProbeEvent(event) {
              sse.send(event);
            },
            suppressOpeningText: true,
            suppressClosingText: true,
          });
          emitProbeStage('route_request_done');

          if (routerResult.content instanceof ReadableStream) {
            emitProbeStage('readable_stream_started');
            await processOpenAIStream(routerResult.content, appendAssistantDelta);
            emitProbeStage('readable_stream_done');
          } else if (routerResult.content) {
            emitProbeStage('buffered_content_started');
            for (const chunk of chunkText(String(routerResult.content))) {
              appendAssistantDelta(chunk);
            }
            emitProbeStage('buffered_content_done');
          }

          if (routerResult.trailingContent) {
            appendAssistantDelta(routerResult.trailingContent);
          }

          sse.send({
            type: 'final',
            content: streamedContent,
            metadata: routerResult.metadata,
            sources: routerResult.sources,
          });
          emitProbeStage('pipeline_done');
        } catch (error) {
          const errorMessage = formatAgentError(error);
          emitProbeStage('pipeline_failed', { error: errorMessage });
          const fallbackContent = streamedContent || `请求处理失败：${errorMessage}`;
          if (!streamedContent) {
            sse.send({ type: 'delta', delta: fallbackContent });
          }
          sse.send({
            type: 'final',
            content: fallbackContent,
            metadata: {
              status: 'error',
              stream_error: errorMessage,
            },
          });
        } finally {
          sse.done();
          controller.close();
        }
      },
    });

    return sseResponse(stream);
  }

  async function handleReportSummary(env: any, payload: ReportSummaryPayload): Promise<ChatReply> {
    const toolCall = buildReportSummaryToolCall(payload);
    const turnContext: ChatTurnContext = {
      routingMode: DEFAULT_RULE_ROUTING_MODE,
      variantContext: null,
    };
    const reportEnvOverride = buildReportEnvOverride(env);

    const routerResult = await deps.routeRequest(env, encodeInternalWorkerToolCall(toolCall), [], {
      turnContext,
      suppressStageText: true,
      reportEnvOverride,
    });
    const baseContent = typeof routerResult.content === 'string' ? routerResult.content : '';
    const metadata: Record<string, unknown> = {
      ...(routerResult.metadata ?? {}),
      tool:
        typeof routerResult.metadata?.tool === 'string'
          ? routerResult.metadata.tool
          : toolCall.tool,
    };
    const formattedBaseContent = formatStructuredOutput(
      baseContent,
      metadata,
      env as OutputFormatterEnv
    );
    const assistantContent = formattedBaseContent;

    return {
      role: 'assistant',
      content: assistantContent,
      sources: routerResult.sources,
      metadata,
      tools: Array.isArray(metadata.tools) ? (metadata.tools as unknown[]) : [],
    };
  }

  function sendInactiveRunStream(
    sse: ReturnType<typeof createSseWriter>,
    run: SessionRunRecord
  ): void {
    const reply = buildInactiveRunReply(run);
    const message: AgentMessage = {
      id: deps.createId('msg'),
      role: 'assistant',
      content: reply.content,
      createdAt: new Date().toISOString(),
      status: 'complete',
      metadata: reply.metadata,
      tools: reply.tools,
    };
    sse.send({ type: 'start', run_id: run.id });
    sse.send({ type: 'delta', run_id: run.id, delta: reply.content });
    sse.send({ type: 'final', run_id: run.id, message });
  }

  async function createQueuedRun(
    env: any,
    sessionId: string,
    content: string,
    mode: SessionRunMode
  ): Promise<SessionRunRecord> {
    return sessionRunRepository.createQueuedRun(env.DB, {
      id: deps.createId('run'),
      sessionId,
      mode,
      content,
    });
  }

  async function waitForRunStart(env: any, runId: string): Promise<SessionRunRecord | null> {
    const leaseOwner = deps.createId('lease');
    const startedWaitingAt = Date.now();

    for (;;) {
      const leaseExpiresAt = new Date(Date.now() + RUN_LEASE_MS).toISOString();
      const staleRunningStartedBefore = new Date(Date.now() - RUN_STALE_RUNNING_MS).toISOString();
      const startedRun = await sessionRunRepository.tryStartRun(
        env.DB,
        runId,
        leaseOwner,
        leaseExpiresAt,
        staleRunningStartedBefore
      );
      if (startedRun) {
        return startedRun;
      }

      const run = await sessionRunRepository.getRun(env.DB, runId);
      if (
        !run ||
        run.status === 'cancelled' ||
        run.status === 'failed' ||
        run.status === 'completed'
      ) {
        return null;
      }

      if (Date.now() - startedWaitingAt > RUN_ACQUIRE_TIMEOUT_MS) {
        await sessionRunRepository.failRun(
          env.DB,
          runId,
          'Timed out waiting for the session to become available.'
        );
        return null;
      }

      await sleep(RUN_ACQUIRE_POLL_MS);
    }
  }

  function buildInactiveRunReply(run: SessionRunRecord): ChatReply {
    if (run.response_json) {
      try {
        const parsed = JSON.parse(run.response_json);
        if (parsed && typeof parsed === 'object') {
          const reply = parsed as Partial<ChatReply>;
          return {
            role: 'assistant',
            content: String(reply.content || 'This request was replaced by a newer message.'),
            metadata: reply.metadata,
            tools: Array.isArray(reply.tools) ? reply.tools : [],
          };
        }
      } catch {
        // Fall through to the default inactive run reply.
      }
    }

    return {
      role: 'assistant',
      content: run.error_message || 'This request was replaced by a newer message.',
      metadata: {
        session_run_id: run.id,
        session_run_status: run.status,
        superseded_by_run_id: run.superseded_by_run_id,
      },
      tools: [],
    };
  }

  return {
    handleChat,
    handleChatStream,
    handleDirectStreamProbe,
    handlePipelineStreamProbe,
    handleReportSummary,
  };
}

function buildReportSummaryToolCall(payload: ReportSummaryPayload): {
  tool: StructuredLookupToolName;
  args: Record<string, unknown>;
} {
  const partition = payload.ppartition?.trim();
  const accidentDate = payload.accidentDate?.trim();
  const withPartition = (args: Record<string, unknown>) => ({
    ...args,
    ...(partition ? { ppartition: partition } : {}),
  });

  if (payload.type === 'driver') {
    return {
      tool: 'generate_driver_report',
      args: withPartition({ driver_name: payload.nameOrId }),
    };
  }
  if (payload.type === 'vehicle') {
    return {
      tool: 'generate_vehicle_report',
      args: withPartition({ numberPlate: payload.nameOrId }),
    };
  }
  if (payload.type === 'unit') {
    return {
      tool: 'generate_unit_report',
      args: withPartition({ organ_name: payload.nameOrId }),
    };
  }
  if (payload.type === 'route') {
    return {
      tool: 'generate_route_report',
      args: withPartition({ route_name: payload.nameOrId }),
    };
  }
  if (payload.type === 'station') {
    return {
      tool: 'generate_station_report',
      args: withPartition({ station_name: payload.nameOrId }),
    };
  }
  return {
    tool: 'generate_accident_investigation_report',
    args: { driver_name: payload.nameOrId, accident_date: accidentDate ?? '' },
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function buildStreamFallbackContent(partialContent: string, errorMessage: string): string {
  const detail = errorMessage.trim() || 'Unknown stream error.';
  const fallback = `\n\n请求处理失败，实际错误：${detail}`;
  return partialContent ? `${partialContent}${fallback}` : `请求处理失败，实际错误：${detail}`;
}
