import { config } from '../config';

type ChatMessage = {
  role: 'system' | 'user' | 'assistant';
  content: string;
};

function normalizeBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.replace(/\/+$/, '');
  const withoutChat = trimmed.replace(/\/chat\/completions$/, '');
  if (withoutChat.endsWith('/v1')) {
    return withoutChat;
  }
  return `${withoutChat}/v1`;
}

function extractJsonText(content: string): string {
  const trimmed = content.trim();
  if (!trimmed) return '';
  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]+?)```/i);
  if (fenced?.[1]) {
    return fenced[1].trim();
  }
  return trimmed;
}

export async function callLlmJson<T>(
  model: string,
  messages: ChatMessage[],
  fallback: T
): Promise<T> {
  if (!config.llmBaseUrl) {
    return fallback;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.requestTimeoutMs);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (config.llmApiKey) {
    headers.Authorization = `Bearer ${config.llmApiKey}`;
  }

  try {
    const response = await fetch(`${normalizeBaseUrl(config.llmBaseUrl)}/chat/completions`, {
      method: 'POST',
      headers,
      signal: controller.signal,
      body: JSON.stringify({
        model,
        temperature: 0,
        messages,
        response_format: { type: 'json_object' },
      }),
    });

    if (!response.ok) {
      return fallback;
    }

    const payload = (await response.json()) as {
      choices?: Array<{
        message?: {
          content?: string;
        };
      }>;
    };
    const raw = payload.choices?.[0]?.message?.content;
    if (!raw || typeof raw !== 'string') {
      return fallback;
    }
    const jsonText = extractJsonText(raw);
    return JSON.parse(jsonText) as T;
  } catch {
    return fallback;
  } finally {
    clearTimeout(timeout);
  }
}
