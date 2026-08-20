import { config } from '../config';
import { callLlmJson } from './llm';

export interface RerankCandidate {
  doc_id: string;
  clause_id: string;
  title: string;
  field_path: string;
  heading_path: string[];
  content_excerpt: string;
  coarse_score: number;
}

interface RerankResultItem {
  clause_id: string;
  score: number;
  reason?: string;
}

interface RerankPayload {
  results: RerankResultItem[];
}

function clampScore(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export async function rerankRetrieveCandidates(
  query: string,
  candidates: RerankCandidate[]
): Promise<Map<string, number> | null> {
  if (!config.retrieveRerankEnabled || candidates.length === 0) {
    return null;
  }

  const fallback: RerankPayload = { results: [] };
  const payload = await callLlmJson<RerankPayload | null>(
    config.rerankModel,
    [
      {
        role: 'system',
        content: [
          '你是知识库条款重排器，只判断哪条最能直接回答用户问题，不要回答问题。',
          '输出必须是 JSON 对象，字段固定为 results。',
          'results 是数组，每项包含 clause_id、score、reason。',
          'score 范围 0 到 1。',
          '偏向直接可回答“规定/要求/职责/流程/时限/禁止”的证据。',
          '主题相近但不能直接回答的候选必须低分。',
          '如问题在问怎么办、是否允许、谁负责、何时上报，优先操作性条款。',
        ].join('\n'),
      },
      {
        role: 'user',
        content: JSON.stringify(
          {
            query: query.trim(),
            candidates,
          },
          null,
          2
        ),
      },
    ],
    fallback
  );

  if (!payload || !Array.isArray(payload.results)) {
    return null;
  }

  const scoreMap = new Map<string, number>();
  for (const item of payload.results) {
    if (!item || typeof item.clause_id !== 'string' || !item.clause_id.trim()) continue;
    scoreMap.set(item.clause_id.trim(), clampScore(item.score));
  }
  return scoreMap;
}
