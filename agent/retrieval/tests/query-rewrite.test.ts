import { describe, expect, it } from 'vitest';
import { buildRewriteFallback, splitKeywordQuery } from '../src/services/query-rewrite';

describe('query rewrite fallback', () => {
  it('splits lexical keywords and preserves the original query as dense query', () => {
    const result = buildRewriteFallback('事故后多久要上报');

    expect(result.original_query).toBe('事故后多久要上报');
    expect(result.dense_query).toBe('事故后多久要上报');
    expect(result.lexical_queries.length).toBeGreaterThanOrEqual(1);
  });

  it('deduplicates keyword tokens', () => {
    expect(splitKeywordQuery('投诉 投诉 处理')).toEqual(['投诉', '处理']);
  });
});
