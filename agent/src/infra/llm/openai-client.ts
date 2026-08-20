export interface EmbeddingEnvLike {
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_EMBEDDING_MODEL?: string;
  EMBEDDING_MODEL?: string;
}

export function normalizeBaseUrl(baseUrl?: string): string {
  const trimmed = (baseUrl || 'https://dashscope.aliyuncs.com/compatible-mode/v1').replace(/\/+$/, '');
  const withoutChat = trimmed.replace(/\/chat\/completions$/, '');
  if (withoutChat.endsWith('/v1')) {
    return withoutChat;
  }
  return `${withoutChat}/v1`;
}

export async function callOpenAIEmbedding(
  env: EmbeddingEnvLike,
  input: string,
  defaultModel = 'text-embedding-v1'
): Promise<number[]> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const apiKey = env.OPENAI_API_KEY?.trim();
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }

  const response = await fetch(`${normalizeBaseUrl(env.OPENAI_BASE_URL)}/embeddings`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model: env.OPENAI_EMBEDDING_MODEL || env.EMBEDDING_MODEL || defaultModel,
      input,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`embedding request failed: ${response.status} ${errorText}`);
  }

  const payload = (await response.json()) as {
    data?: Array<{ embedding?: number[] }>;
  };
  const embedding = payload.data?.[0]?.embedding;
  if (!embedding || !Array.isArray(embedding)) {
    throw new Error('embedding response missing vector');
  }
  return embedding;
}
