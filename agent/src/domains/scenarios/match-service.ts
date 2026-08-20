import { callOpenAIEmbedding } from '../../infra/llm/openai-client';
import { cosineSimilarity } from '../../shared/vector';
import type { WorkScenario } from './repository';

interface ScenarioEnvLike {
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_EMBEDDING_MODEL?: string;
}

export type ScenarioMatchMethod = 'vector' | 'none';

export interface ScenarioMatchCandidate {
  scenario: WorkScenario;
  score: number;
  method: ScenarioMatchMethod;
}

export interface ScenarioMatchResult {
  matched: boolean;
  method: ScenarioMatchMethod;
  best?: ScenarioMatchCandidate;
  candidates: ScenarioMatchCandidate[];
  reason?: string;
}

export interface ScenarioMatchOptions {
  topK?: number;
  queryEmbedding?: number[];
}

export function buildScenarioEmbeddingText(input: {
  name: string;
  description: string;
  keywords?: string[];
}): string {
  const parts = [input.name, input.description];
  if (input.keywords?.length) {
    parts.push(`keywords: ${input.keywords.join(', ')}`);
  }
  return parts.filter(Boolean).join('\n');
}

export async function tryGenerateScenarioEmbedding(
  env: ScenarioEnvLike,
  input: { name: string; description: string; keywords?: string[] }
): Promise<number[] | null> {
  try {
    return await callOpenAIEmbedding(env, buildScenarioEmbeddingText(input));
  } catch (error) {
    console.warn('Scenario embedding failed:', error);
    return null;
  }
}

export async function matchWorkScenario(
  env: ScenarioEnvLike,
  query: string,
  scenarios: WorkScenario[],
  options: number | ScenarioMatchOptions = 6
): Promise<ScenarioMatchResult> {
  const topK = typeof options === 'number' ? options : options.topK ?? 6;
  const sharedQueryEmbedding =
    typeof options === 'number'
      ? undefined
      : Array.isArray(options.queryEmbedding) && options.queryEmbedding.length
        ? options.queryEmbedding
        : undefined;
  const enabledScenarios = scenarios.filter((scenario) => scenario.enabled);
  if (!enabledScenarios.length) {
    return {
      matched: false,
      method: 'none',
      candidates: [],
      reason: 'empty',
    };
  }

  const vectorCandidates = enabledScenarios.filter(
    (scenario) => Array.isArray(scenario.embedding) && scenario.embedding.length > 0
  );

  let vectorFailed = false;
  if (vectorCandidates.length) {
    try {
      const queryEmbedding = sharedQueryEmbedding ?? (await callOpenAIEmbedding(env, query));
      const candidates = vectorCandidates
        .map(
          (scenario): ScenarioMatchCandidate => ({
            scenario,
            score: cosineSimilarity(queryEmbedding, scenario.embedding as number[]),
            method: 'vector',
          })
        )
        .sort((left, right) => right.score - left.score);

      return {
        matched: false,
        method: 'vector',
        best: candidates[0],
        candidates: candidates.slice(0, topK),
      };
    } catch (error) {
      vectorFailed = true;
      console.warn('Vector match failed, using all scenarios:', error);
    }
  }

  const fallbackCandidates = enabledScenarios.slice(0, topK).map((scenario) => ({
    scenario,
    score: 0,
    method: 'none' as const,
  }));

  return {
    matched: false,
    method: vectorFailed ? 'none' : 'vector',
    best: fallbackCandidates[0],
    candidates: fallbackCandidates,
    reason: vectorFailed ? 'embedding_failed' : 'no_vector_candidates',
  };
}
