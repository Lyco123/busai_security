import { describe, expect, it } from 'vitest';
import { buildEmbeddingText, deriveHeadingPath, parseDocumentForPreview } from '../src/services/document-parser';

function makeInput(text: string, splitOptions?: { min_clause_chars?: number; max_clause_chars?: number }) {
  return {
    file_name: 'sample.txt',
    file_mime: 'text/plain',
    content: Buffer.from(text, 'utf8'),
    split_options: splitOptions,
  };
}

describe('document parser', () => {
  it('keeps chapter as context and does not emit heading-only article chunks', async () => {
    const result = await parseDocumentForPreview(
      makeInput(['第一章 总则', '', '第十二条', '（一）适用范围。', '（二）管理要求。'].join('\n'))
    );

    expect(result.warnings).toEqual([]);
    expect(result.clauses).toHaveLength(2);
    expect(result.clauses[0].field_path).toBe('第一章 总则/第十二条/（一）');
    expect(result.clauses[0].heading_path).toEqual(['第一章 总则', '第十二条', '（一）']);
    expect(result.clauses[0].content).toBe(['（一）', '适用范围。'].join('\n'));
    expect(result.clauses[1].field_path).toBe('第一章 总则/第十二条/（二）');
    expect(result.clauses.every((item) => item.content !== '第十二条')).toBe(true);
  });

  it('merges short body forward and preserves both article titles in content', async () => {
    const result = await parseDocumentForPreview(
      makeInput(
        ['第一章 总则', '', '第十二条 目的。', '', '第十三条 为了进一步规范管理，制定本办法。'].join('\n'),
        { min_clause_chars: 10, max_clause_chars: 200 }
      )
    );

    expect(result.clauses).toHaveLength(1);
    expect(result.clauses[0].field_path).toBe('第一章 总则/第十二条');
    expect(result.clauses[0].heading_path).toEqual(['第一章 总则', '第十二条']);
    expect(result.clauses[0].content).toContain('第十二条');
    expect(result.clauses[0].content).toContain('目的。');
    expect(result.clauses[0].content).toContain('第十三条');
    expect(result.clauses[0].content).toContain('为了进一步规范管理');
  });

  it('preserves the merged sibling article title in content', async () => {
    const result = await parseDocumentForPreview(
      makeInput(
        ['第一章 总则', '', '第二条 本规定适用于集团直属单位。', '', '第三条 本规定的服务投诉包括热线、官网和来访。'].join('\n'),
        { min_clause_chars: 40, max_clause_chars: 200 }
      )
    );

    expect(result.warnings).toEqual([]);
    expect(result.clauses).toHaveLength(1);
    expect(result.clauses[0].field_path).toBe('第一章 总则/第二条');
    expect(result.clauses[0].heading_path).toEqual(['第一章 总则', '第二条']);
    expect(result.clauses[0].content).toContain('第二条');
    expect(result.clauses[0].content).toContain('本规定适用于集团直属单位');
    expect(result.clauses[0].content).toContain('第三条');
    expect(result.clauses[0].content).toContain('服务投诉包括热线、官网和来访');
  });

  it('preserves parent article and child item titles when merging forward', async () => {
    const result = await parseDocumentForPreview(
      makeInput(
        [
          '第一章 总则',
          '',
          '第五条 巴士集团及各直属单位应当定期或不定期开展消防安全教育和培训，加强消防应急演练。',
          '（一）各直属单位应当按巴士集团灭火和应急疏散的相关预案，确定疏散引导人员。',
          '（二）各直属单位每年至少组织一次消防演练。',
        ].join('\n'),
        { min_clause_chars: 120, max_clause_chars: 500 }
      )
    );

    expect(result.clauses).toHaveLength(2);
    expect(result.clauses[0].field_path).toBe('第一章 总则/第五条');
    expect(result.clauses[0].content).toContain('第五条');
    expect(result.clauses[0].content).toContain('开展消防安全教育和培训');
    expect(result.clauses[0].content).toContain('（一）');
    expect(result.clauses[0].content).toContain('疏散引导人员');
    expect(result.clauses[1].field_path).toBe('第一章 总则/第五条/（二）');
    expect(result.clauses[1].content).toContain('消防演练');
  });

  it('merges a short final article backward within the same chapter', async () => {
    const result = await parseDocumentForPreview(
      makeInput(
        [
          '第一章 总则',
          '',
          '第一条 本条内容足够长，用于承载本章末尾的短条款，并保持章内语义稳定。',
          '第二条 末尾短条。',
          '第二章 附则',
          '第三条 本条属于下一章，内容足够长，不应被第一章末尾短条款向后吞并，并且需要保持独立的章节上下文用于检索。',
        ].join('\n'),
        { min_clause_chars: 30, max_clause_chars: 300 }
      )
    );

    expect(result.clauses).toHaveLength(2);
    expect(result.clauses[0].field_path).toBe('第一章 总则/第一条');
    expect(result.clauses[0].content).toContain('第一条');
    expect(result.clauses[0].content).toContain('第二条');
    expect(result.clauses[0].content).toContain('末尾短条');
    expect(result.clauses[1].field_path).toBe('第二章 附则/第三条');
    expect(result.clauses[1].content).not.toContain('第二条');
  });

  it('merges a single short chapter backward into the previous chapter', async () => {
    const result = await parseDocumentForPreview(
      makeInput(
        [
          '第一章 总则',
          '',
          '第一条 本章内容足够长，可作为后续过短章节的合并目标，避免短章节向后跨到下一章。',
          '第二章 简短章',
          '第二条 短章。',
          '第三章 附则',
          '第三条 本条属于后续章节，内容足够长，应保持独立并避免被短章向后合并，同时保留后续章节自身的语义。',
        ].join('\n'),
        { min_clause_chars: 30, max_clause_chars: 300 }
      )
    );

    expect(result.clauses).toHaveLength(2);
    expect(result.clauses[0].field_path).toBe('第一章 总则/第一条');
    expect(result.clauses[0].content).toContain('第二章 简短章');
    expect(result.clauses[0].content).toContain('第二条');
    expect(result.clauses[0].content).toContain('短章');
    expect(result.clauses[1].field_path).toBe('第三章 附则/第三条');
    expect(result.clauses[1].content).not.toContain('第二条');
  });

  it('falls back to paragraph chunks while preserving parent heading context', async () => {
    const result = await parseDocumentForPreview(
      makeInput(['第一章 总则', '', '适用范围说明。', '', '管理要求说明。'].join('\n'), {
        min_clause_chars: 20,
        max_clause_chars: 80,
      })
    );

    expect(result.warnings).toContain('AUTO_SPLIT_FALLBACK_PARAGRAPH');
    expect(result.clauses).toHaveLength(1);
    expect(result.clauses[0].field_path).toBe('第一章 总则');
    expect(result.clauses[0].heading_path).toEqual(['第一章 总则']);
    expect(result.clauses[0].content).toContain('适用范围说明。');
    expect(result.clauses[0].content).toContain('管理要求说明。');
  });

  it('derives heading path from stored field path and builds embedding text with context', () => {
    expect(deriveHeadingPath('第一章 总则/第十二条/（一）')).toEqual(['第一章 总则', '第十二条', '（一）']);
    expect(deriveHeadingPath('paragraph/1')).toEqual(['paragraph/1']);
    expect(buildEmbeddingText('制度标题', '第一章 总则/第十二条', '正文内容')).toBe(
      ['制度标题', '第一章 总则/第十二条', '正文内容'].join('\n')
    );
  });
});
