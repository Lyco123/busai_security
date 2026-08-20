import { config } from '../config';

interface EmbeddingResponsePayload {
  data?: Array<{ embedding?: number[] }>;
}

function validateEmbedding(vector: unknown): number[] {
  if (!Array.isArray(vector) || vector.length !== config.embedDim) {
    throw new Error(`Embedding dimension mismatch, expected ${config.embedDim}`);
  }
  if (vector.some((item) => typeof item !== 'number' || !Number.isFinite(item))) {
    throw new Error('Embedding contains invalid numeric values');
  }
  return vector as number[];
}

export async function generateEmbedding(input: string): Promise<number[]> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.requestTimeoutMs);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (config.embeddingApiKey) {
    headers.Authorization = `Bearer ${config.embeddingApiKey}`;
  }

  try {
    const response = await fetch(`${config.embeddingBaseUrl.replace(/\/+$/, '')}/embeddings`, {
      method: 'POST',
      headers,
      signal: controller.signal,
      body: JSON.stringify({
        model: config.embeddingModel,
        input,
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Embedding request failed: ${response.status} ${detail.slice(0, 200)}`);
    }

    const payload = (await response.json()) as EmbeddingResponsePayload;
    const vector = payload.data?.[0]?.embedding;
    return validateEmbedding(vector);
  } finally {
    clearTimeout(timeout);
  }
}
