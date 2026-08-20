import { safeJsonParse } from '../../shared/json';
import { normalizeBaseUrl } from './openai-client';

export type ChatCompletionRole = 'user' | 'assistant' | 'system' | 'tool';

export interface ChatToolCall<TToolName extends string = string> {
  id: string;
  tool: TToolName;
  args: Record<string, unknown>;
}

export interface ChatCompletionMessage<TToolName extends string = string> {
  role: ChatCompletionRole;
  content: string;
  tool_call_id?: string;
  name?: string;
  tool_calls?: Array<ChatToolCall<TToolName>>;
}

export interface ToolSchema<TToolName extends string = string> {
  name: TToolName;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export type OpenAITool<TToolName extends string = string> = {
  type: 'function';
  function: ToolSchema<TToolName>;
};

export interface OpenAIChatEnvLike {
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_LOCAL_BASE_URL?: string;
  OPENAI_LOCAL_MODEL?: string;
  OPENAI_API_TIMEOUT_MS?: string;
  OPENAI_STREAM_DIAGNOSTICS?: string;
}

export interface ChatToolCallDelta<TToolName extends string = string> {
  index: number;
  id?: string;
  tool?: TToolName;
  argumentsDelta?: string;
}

export type ChatReasoningDelta = {
  delta: string;
  field: 'reasoning' | 'reasoning_content';
};

export interface StreamedChatCompletionTurn<TToolName extends string = string> {
  content?: string;
  toolCalls?: Array<ChatToolCall<TToolName>>;
  finishReason?: string;
  reasoning?: string;
}

function resolveOpenAITimeoutMs(env: OpenAIChatEnvLike): number {
  const value = Number(env.OPENAI_API_TIMEOUT_MS ?? '45000');
  if (!Number.isFinite(value) || value <= 0) {
    return 45000;
  }
  return Math.floor(value);
}

function isOpenAIStreamDiagnosticsEnabled(env: OpenAIChatEnvLike): boolean {
  return String(env.OPENAI_STREAM_DIAGNOSTICS ?? '').trim().toLowerCase() === 'true';
}

function isOpenAIStreamVerboseDiagnosticsEnabled(env: OpenAIChatEnvLike): boolean {
  return String((env as Record<string, unknown>).OPENAI_STREAM_VERBOSE_DIAGNOSTICS ?? '')
    .trim()
    .toLowerCase() === 'true';
}

function previewDiagnosticText(value: string, limit = 180): string {
  return value.replace(/\s+/g, ' ').trim().slice(0, limit);
}

function extractOpenAIErrorMessage(value: unknown): string | null {
  if (!isRecord(value) || !isRecord(value.error)) {
    return null;
  }
  const error = value.error;
  const message = typeof error.message === 'string' ? error.message.trim() : '';
  const code =
    typeof error.code === 'string' || typeof error.code === 'number'
      ? String(error.code)
      : '';
  const type = typeof error.type === 'string' ? error.type.trim() : '';
  return [code, type, message].filter(Boolean).join(' ');
}

function emitOpenAIStreamDiagnostic(
  env: OpenAIChatEnvLike,
  stage: string,
  payload: Record<string, unknown>
): void {
  if (!isOpenAIStreamDiagnosticsEnabled(env)) {
    return;
  }
  console.log(
    `[openai-stream-diagnostic] ${stage} ${JSON.stringify({
      ts: new Date().toISOString(),
      ...payload,
    })}`
  );
}

function emitVerboseOpenAIStreamDiagnostic(
  env: OpenAIChatEnvLike,
  stage: string,
  payload: Record<string, unknown>
): void {
  if (!isOpenAIStreamVerboseDiagnosticsEnabled(env)) {
    return;
  }
  emitOpenAIStreamDiagnostic(env, stage, payload);
}

function buildThinkingFields(
  env: OpenAIChatEnvLike,
  enableThinking?: boolean
): Record<string, unknown> {
  const baseUrl = String(env.OPENAI_BASE_URL ?? '').toLowerCase();
  const isDashScope = !baseUrl || baseUrl.includes('dashscope.aliyuncs.com');
  if (isDashScope) {
    return enableThinking === undefined ? {} : { enable_thinking: enableThinking };
  }
  if (enableThinking === undefined) {
    return {};
  }
  return {
    chat_template_kwargs: {
      enable_thinking: enableThinking,
    },
  };
}

function getLocalOpenAIEnv(env: OpenAIChatEnvLike): OpenAIChatEnvLike | null {
  const baseUrl = env.OPENAI_LOCAL_BASE_URL?.trim();
  const model = env.OPENAI_LOCAL_MODEL?.trim();
  if (!baseUrl || !model) {
    return null;
  }
  return {
    ...env,
    OPENAI_BASE_URL: baseUrl,
    OPENAI_API_KEY: undefined,
  };
}

async function fetchOpenAIChatCompletion(
  env: OpenAIChatEnvLike,
  model: string,
  buildBody: (requestEnv: OpenAIChatEnvLike, requestModel: string) => Record<string, unknown>
): Promise<Response> {
  const localEnv = getLocalOpenAIEnv(env);
  const candidates = localEnv
    ? [
        { env: localEnv, model: env.OPENAI_LOCAL_MODEL!.trim(), name: 'local' },
        { env, model, name: 'fallback' },
      ]
    : [{ env, model, name: 'default' }];

  let localError: string | null = null;
  for (const candidate of candidates) {
    let response: Response;
    try {
      response = await fetchWithTimeout(
        candidate.env,
        `${normalizeBaseUrl(candidate.env.OPENAI_BASE_URL)}/chat/completions`,
        {
          method: 'POST',
          headers: buildHeaders(candidate.env),
          body: JSON.stringify(buildBody(candidate.env, candidate.model)),
        }
      );
    } catch (error) {
      if (candidate.name !== 'local') {
        throw error;
      }
      localError = error instanceof Error ? error.message : String(error);
      console.warn(`[openai-local-fallback] local model request failed, fallback to default: ${localError}`);
      continue;
    }
    if (response.ok || candidate.name !== 'local') {
      return response;
    }
    localError = await response.text().catch(() => '');
    console.warn(
      `[openai-local-fallback] local model request failed, fallback to default: ${response.status} ${localError.slice(0, 180)}`
    );
  }

  throw new Error(localError || 'OpenAI request failed');
}

async function fetchWithTimeout(
  env: OpenAIChatEnvLike,
  url: string,
  init: RequestInit
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), resolveOpenAITimeoutMs(env));
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('OpenAI request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function callOpenAI(
  env: OpenAIChatEnvLike,
  options: {
    model: string;
    messages: Array<ChatCompletionMessage>;
    temperature?: number;
    responseFormat?: 'json_object';
    enableThinking?: boolean;
  }
): Promise<string> {
  const response = await fetchOpenAIChatCompletion(env, options.model, (requestEnv, requestModel) => ({
      model: requestModel,
      messages: formatMessagesForOpenAI(options.messages.filter((message) => message.role !== 'tool')),
      temperature: options.temperature ?? 0.4,
      response_format: options.responseFormat ? { type: options.responseFormat } : undefined,
      ...buildThinkingFields(requestEnv, options.enableThinking),
  }));

  await assertOk(response);

  const payload = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  const content = payload.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error('模型响应为空');
  }
  return content.trim();
}

export async function callOpenAIWithTools<TToolName extends string>(
  env: OpenAIChatEnvLike,
  options: {
    model: string;
    messages: Array<ChatCompletionMessage<TToolName>>;
    temperature?: number;
    tools: Array<OpenAITool<TToolName>>;
    createToolCallId?: (prefix: string) => string;
    enableThinking?: boolean;
  }
): Promise<{ content?: string; toolCalls?: Array<ChatToolCall<TToolName>> }> {
  const response = await fetchOpenAIChatCompletion(env, options.model, (requestEnv, requestModel) => ({
      model: requestModel,
      messages: formatMessagesForOpenAI(options.messages),
      temperature: options.temperature ?? 0.2,
      tools: options.tools,
      tool_choice: 'auto',
      ...(options.enableThinking === false && options.tools.length
        ? {}
        : buildThinkingFields(requestEnv, options.enableThinking)),
  }));

  await assertOk(response);

  const message = await readFirstMessage(response);
  const toolCalls = parseToolCalls<TToolName>(message?.tool_calls, options.createToolCallId);

  return {
    content: message?.content?.trim() || undefined,
    toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
  };
}

export async function callOpenAIStreamWithTools<TToolName extends string>(
  env: OpenAIChatEnvLike,
  options: {
    model: string;
    messages: Array<ChatCompletionMessage<TToolName>>;
    temperature?: number;
    tools: Array<OpenAITool<TToolName>>;
    enableThinking?: boolean;
  }
): Promise<ReadableStream> {
  const response = await fetchOpenAIChatCompletion(env, options.model, (requestEnv, requestModel) => ({
      model: requestModel,
      messages: formatMessagesForOpenAI(options.messages),
      temperature: options.temperature ?? 0.2,
      tools: options.tools,
      tool_choice: 'none',
      stream: true,
      ...(options.enableThinking === false && options.tools.length
        ? {}
        : buildThinkingFields(requestEnv, options.enableThinking)),
  }));

  await assertOk(response);
  return response.body!;
}

export async function callOpenAIWithToolsStream<TToolName extends string>(
  env: OpenAIChatEnvLike,
  options: {
    model: string;
    messages: Array<ChatCompletionMessage<TToolName>>;
    temperature?: number;
    tools: Array<OpenAITool<TToolName>>;
    toolChoice?: 'auto' | 'none';
    createToolCallId?: (prefix: string) => string;
    onTextDelta?: (delta: string) => void;
    onReasoningDelta?: (delta: ChatReasoningDelta) => void;
    onToolCallDelta?: (delta: ChatToolCallDelta<TToolName>) => void;
    onToolCallReady?: (toolCall: ChatToolCall<TToolName>) => void;
    enableThinking?: boolean;
  }
): Promise<StreamedChatCompletionTurn<TToolName>> {
  const response = await fetchOpenAIChatCompletion(env, options.model, (requestEnv, requestModel) => ({
      model: requestModel,
      messages: formatMessagesForOpenAI(options.messages),
      temperature: options.temperature ?? 0.2,
      ...(options.tools.length ? { tools: options.tools, tool_choice: options.toolChoice ?? 'auto' } : {}),
      stream: true,
      ...(options.enableThinking === false && options.tools.length
        ? {}
        : buildThinkingFields(requestEnv, options.enableThinking)),
  }));

  await assertOk(response);
  if (!response.body) {
    throw new Error('妯″瀷鏈嶅姟鏈繑鍥炴祦寮忓搷搴斾綋');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const toolCallBuilders = new Map<
    number,
    { id: string; name: string; argumentsText: string }
  >();
  let buffer = '';
  let content = '';
  let reasoning = '';
  let finishReason = '';
  let upstreamChunkCount = 0;
  let upstreamEventCount = 0;
  let upstreamBytes = 0;
  let textDeltaCount = 0;
  let reasoningDeltaCount = 0;

  const handlePayload = (payloadText: string) => {
    if (!payloadText || payloadText === '[DONE]') {
      return;
    }
    const payload = JSON.parse(payloadText) as OpenAIStreamChunk;
    const errorMessage = extractOpenAIErrorMessage(payload);
    if (errorMessage) {
      throw new Error(`Model stream error: ${errorMessage}`);
    }
    const choice = payload.choices?.[0];
    if (!choice) {
      return;
    }
    if (typeof choice.finish_reason === 'string') {
      finishReason = choice.finish_reason;
    }
    const delta = choice.delta;
    if (!delta) {
      return;
    }
    if (typeof delta.content === 'string' && delta.content.length > 0) {
      content += delta.content;
      textDeltaCount += 1;
      emitVerboseOpenAIStreamDiagnostic(env, 'text-delta', {
        length: delta.content.length,
        preview: previewDiagnosticText(delta.content, 96),
      });
      options.onTextDelta?.(delta.content);
    }
    const reasoningDelta =
      typeof delta.reasoning_content === 'string' && delta.reasoning_content.length > 0
        ? { field: 'reasoning_content' as const, delta: delta.reasoning_content }
        : typeof delta.reasoning === 'string' && delta.reasoning.length > 0
          ? { field: 'reasoning' as const, delta: delta.reasoning }
          : null;
    if (reasoningDelta) {
      reasoning += reasoningDelta.delta;
      reasoningDeltaCount += 1;
      emitVerboseOpenAIStreamDiagnostic(env, 'reasoning-delta', {
        field: reasoningDelta.field,
        length: reasoningDelta.delta.length,
        preview: previewDiagnosticText(reasoningDelta.delta, 96),
      });
      options.onReasoningDelta?.(reasoningDelta);
    }
    for (const toolCallDelta of delta.tool_calls ?? []) {
      const index = typeof toolCallDelta.index === 'number' ? toolCallDelta.index : 0;
      const builder = toolCallBuilders.get(index) ?? { id: '', name: '', argumentsText: '' };
      if (toolCallDelta.id) {
        builder.id = toolCallDelta.id;
      }
      if (toolCallDelta.function?.name) {
        builder.name += toolCallDelta.function.name;
      }
      if (toolCallDelta.function?.arguments) {
        builder.argumentsText += toolCallDelta.function.arguments;
      }
      toolCallBuilders.set(index, builder);
      options.onToolCallDelta?.({
        index,
        id: toolCallDelta.id,
        tool: toolCallDelta.function?.name as TToolName | undefined,
        argumentsDelta: toolCallDelta.function?.arguments,
      });
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      upstreamChunkCount += 1;
      upstreamBytes += value?.byteLength ?? 0;
      emitVerboseOpenAIStreamDiagnostic(env, 'upstream-chunk', {
        bytes: value?.byteLength ?? 0,
      });
      buffer += decoder.decode(value, { stream: true });
      let boundary = findSseBoundary(buffer);
      while (boundary) {
        const rawEvent = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary.length);
        const payloadText = parseSseData(rawEvent);
        if (payloadText) {
          upstreamEventCount += 1;
          emitVerboseOpenAIStreamDiagnostic(env, 'upstream-event', {
            boundary: boundary.length === 4 ? 'crlf' : 'lf',
            length: payloadText.length,
            preview: previewDiagnosticText(payloadText),
          });
          handlePayload(payloadText);
        }
        boundary = findSseBoundary(buffer);
      }
    }

    const tail = decoder.decode();
    if (tail) {
      buffer += tail;
    }
    if (buffer.trim()) {
      const payloadText = parseSseData(buffer);
      if (payloadText) {
        upstreamEventCount += 1;
        handlePayload(payloadText);
      }
    }
  } finally {
    reader.releaseLock();
  }

  emitOpenAIStreamDiagnostic(env, 'stream-summary', {
    upstream_chunks: upstreamChunkCount,
    upstream_events: upstreamEventCount,
    upstream_bytes: upstreamBytes,
    text_delta_count: textDeltaCount,
    reasoning_delta_count: reasoningDeltaCount,
    content_chars: content.length,
    reasoning_chars: reasoning.length,
    finish_reason: finishReason || null,
    tool_call_count: toolCallBuilders.size,
  });

  const toolCalls: Array<ChatToolCall<TToolName>> = [];
  for (const [index, builder] of [...toolCallBuilders.entries()].sort((a, b) => a[0] - b[0])) {
    if (!builder.name) {
      continue;
    }
    const args = safeJsonParse(builder.argumentsText || '{}');
    const parsedArgs = isRecord(args) ? args : {};
    const toolCall = {
      id: builder.id || options.createToolCallId?.('call') || `call_${crypto.randomUUID()}`,
      tool: builder.name as TToolName,
      args: parsedArgs,
    };
    toolCalls.push(toolCall);
    options.onToolCallReady?.(toolCall);
  }

  return {
    content: content.trim() || undefined,
    toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
    finishReason: finishReason || undefined,
    reasoning: reasoning.trim() || undefined,
  };
}

export async function callOpenAIRouter<TToolName extends string>(
  env: OpenAIChatEnvLike,
  options: {
    model: string;
    messages: Array<ChatCompletionMessage<TToolName>>;
    temperature?: number;
    tools: Array<OpenAITool<TToolName>>;
    isRouterToolName: (value: string) => value is TToolName;
    createToolCallId?: (prefix: string) => string;
    enableThinking?: boolean;
  }
): Promise<{ content?: string; toolCall?: ChatToolCall<TToolName> }> {
  const response = await fetchOpenAIChatCompletion(env, options.model, (requestEnv, requestModel) => {
    const requestBody: Record<string, unknown> = {
      model: requestModel,
      messages: formatMessagesForOpenAI(options.messages),
      temperature: options.temperature ?? 0.2,
      ...buildThinkingFields(requestEnv, options.enableThinking),
    };
    if (options.tools.length) {
      requestBody.tools = options.tools;
      requestBody.tool_choice = 'auto';
    }
    return requestBody;
  });

  await assertOk(response);

  const message = await readFirstMessage(response);
  const allowToolCalls = options.tools.length > 0;
  const rawToolCall = allowToolCalls ? message?.tool_calls?.[0] : undefined;
  if (rawToolCall?.function?.name && rawToolCall.function.arguments) {
    const args = safeJsonParse(rawToolCall.function.arguments);
    if (options.isRouterToolName(rawToolCall.function.name) && isRecord(args)) {
      return {
        toolCall: {
          id: rawToolCall.id || options.createToolCallId?.('call') || `call_${crypto.randomUUID()}`,
          tool: rawToolCall.function.name,
          args,
        },
      };
    }
  }

  const content = message?.content?.trim();
  if (allowToolCalls && content) {
    const toolCallFromContent = parseRouterToolCallFromContent(content, options);
    if (toolCallFromContent) {
      return { toolCall: toolCallFromContent };
    }
  }
  return { content: content ?? '' };
}

export async function callOpenAIStream(
  env: OpenAIChatEnvLike,
  options: {
    model: string;
    messages: Array<ChatCompletionMessage>;
    temperature?: number;
    enableThinking?: boolean;
  }
): Promise<ReadableStream> {
  const response = await fetchOpenAIChatCompletion(env, options.model, (requestEnv, requestModel) => ({
      model: requestModel,
      messages: formatMessagesForOpenAI(options.messages.filter((message) => message.role !== 'tool')),
      temperature: options.temperature ?? 0.7,
      stream: true,
      ...buildThinkingFields(requestEnv, options.enableThinking),
  }));

  await assertOk(response);
  return response.body!;
}

function buildHeaders(env: OpenAIChatEnvLike): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const apiKey = env.OPENAI_API_KEY?.trim();
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }
  return headers;
}

function formatMessagesForOpenAI<TToolName extends string>(
  messages: Array<ChatCompletionMessage<TToolName>>
): Array<Record<string, unknown>> {
  return normalizeSystemMessages(messages).map((message) => {
    if (message.role === 'tool') {
      return {
        role: 'tool',
        tool_call_id: message.tool_call_id,
        content: message.content,
      };
    }
    if (message.role === 'assistant' && message.tool_calls?.length) {
      return {
        role: 'assistant',
        content: message.content || null,
        tool_calls: message.tool_calls.map((toolCall) => ({
          id: toolCall.id,
          type: 'function',
          function: {
            name: toolCall.tool,
            arguments: JSON.stringify(toolCall.args),
          },
        })),
      };
    }
    return {
      role: message.role,
      content: message.content,
    };
  });
}

function normalizeSystemMessages<TToolName extends string>(
  messages: Array<ChatCompletionMessage<TToolName>>
): Array<ChatCompletionMessage<TToolName>> {
  const systemMessages = messages.filter((message) => message.role === 'system');
  if (!systemMessages.length) {
    return messages;
  }

  const systemContent = systemMessages
    .map((message) => message.content.trim())
    .filter(Boolean)
    .join('\n\n');
  const nonSystemMessages = messages.filter((message) => message.role !== 'system');
  if (!systemContent) {
    return nonSystemMessages;
  }

  return [{ role: 'system', content: systemContent } as ChatCompletionMessage<TToolName>, ...nonSystemMessages];
}

async function assertOk(response: Response): Promise<void> {
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`模型服务错误：${response.status} ${errorText}`);
  }
}

async function readFirstMessage(response: Response): Promise<OpenAIResponseMessage | undefined> {
  const payload = (await response.json()) as {
    choices?: Array<{ message?: OpenAIResponseMessage }>;
  };
  const errorMessage = extractOpenAIErrorMessage(payload);
  if (errorMessage) {
    throw new Error(`Model response error: ${errorMessage}`);
  }
  return payload.choices?.[0]?.message;
}

function parseSseData(rawEvent: string): string | null {
  const dataLines = rawEvent
    .split('\n')
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith('data:'));
  if (!dataLines.length) {
    return null;
  }
  return dataLines.map((line) => line.replace(/^data:\s?/, '')).join('\n').trim();
}

function findSseBoundary(value: string): { index: number; length: number } | null {
  const lfIndex = value.indexOf('\n\n');
  const crlfIndex = value.indexOf('\r\n\r\n');
  if (lfIndex === -1 && crlfIndex === -1) {
    return null;
  }
  if (lfIndex === -1) {
    return { index: crlfIndex, length: 4 };
  }
  if (crlfIndex === -1) {
    return { index: lfIndex, length: 2 };
  }
  return crlfIndex < lfIndex
    ? { index: crlfIndex, length: 4 }
    : { index: lfIndex, length: 2 };
}

function parseToolCalls<TToolName extends string>(
  rawToolCalls: OpenAIResponseMessage['tool_calls'] | undefined,
  createToolCallId?: (prefix: string) => string
): Array<ChatToolCall<TToolName>> {
  const toolCalls: Array<ChatToolCall<TToolName>> = [];
  for (const rawToolCall of rawToolCalls ?? []) {
    if (!rawToolCall.function?.name || !rawToolCall.function.arguments) {
      continue;
    }
    const args = safeJsonParse(rawToolCall.function.arguments);
    if (isRecord(args)) {
      toolCalls.push({
        id: rawToolCall.id || createToolCallId?.('call') || `call_${crypto.randomUUID()}`,
        tool: rawToolCall.function.name as TToolName,
        args,
      });
    }
  }
  return toolCalls;
}

function parseRouterToolCallFromContent<TToolName extends string>(
  content: string,
  options: {
    isRouterToolName: (value: string) => value is TToolName;
    createToolCallId?: (prefix: string) => string;
  }
): ChatToolCall<TToolName> | null {
  const parsed = safeJsonParse(content);
  if (!isRecord(parsed)) {
    return null;
  }
  const tool = parsed.tool;
  const args = parsed.args;
  if (typeof tool !== 'string' || !options.isRouterToolName(tool) || !isRecord(args)) {
    return null;
  }
  return {
    id: options.createToolCallId?.('call') || `call_${crypto.randomUUID()}`,
    tool,
    args,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

interface OpenAIResponseMessage {
  content?: string;
  tool_calls?: Array<{
    id?: string;
    type?: string;
    function?: { name?: string; arguments?: string };
  }>;
}

interface OpenAIStreamChunk {
  choices?: Array<{
    finish_reason?: string | null;
    delta?: {
      content?: string | null;
      reasoning?: string | null;
      reasoning_content?: string | null;
      tool_calls?: Array<{
        index?: number;
        id?: string;
        type?: string;
        function?: {
          name?: string;
          arguments?: string;
        };
      }>;
    };
  }>;
}
