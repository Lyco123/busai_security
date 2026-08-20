import mammoth from 'mammoth';
import pdfParse from 'pdf-parse';
import { ApiError } from '../utils/errors';
import { parseDocumentWithOcr } from './ocr-client';

export interface ParsedClauseDraft {
  field_path: string;
  heading_path: string[];
  content: string;
  tags: string[];
}

export interface ParsePreviewResult {
  warnings: string[];
  clauses: ParsedClauseDraft[];
}

export interface ParseDocumentInput {
  file_name: string;
  file_mime: string;
  content: Buffer;
  split_options?: {
    min_clause_chars?: number;
    max_clause_chars?: number;
  };
}

type HeadingLevel = 'chapter' | 'section' | 'article' | 'item' | 'subitem';

interface HeadingMatch {
  level: HeadingLevel;
  segment: string;
  inlineBody: string;
  rawLine: string;
}

interface DraftChunk {
  heading_path: string[];
  content: string;
  split_level: HeadingLevel | 'paragraph';
}

interface ExtractTextResult {
  text: string;
  warnings: string[];
}

const SUPPORTED_FILE_TYPES = new Set([
  'text/plain',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/pdf',
]);

const CHINESE_NUM_CLASS =
  '\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\u516d\\u4e03\\u516b\\u4e5d\\u5341\\u767e\\u5343\\u4e07\\u96f6\\u3007\\u4e24';
const CHAPTER_RE = new RegExp(`^(\\u7b2c[${CHINESE_NUM_CLASS}\\d]+\\u7ae0)(?:[\\s:\\uFF1A]+(.*))?$`, 'u');
const SECTION_RE = new RegExp(`^(\\u7b2c[${CHINESE_NUM_CLASS}\\d]+\\u8282)(?:[\\s:\\uFF1A]+(.*))?$`, 'u');
const ARTICLE_RE = new RegExp(`^(\\u7b2c[${CHINESE_NUM_CLASS}\\d]+\\u6761)(?:[\\s:\\uFF1A]+(.*))?$`, 'u');
const ITEM_RE = new RegExp(
  `^(\\uFF08[${CHINESE_NUM_CLASS}]+\\uFF09|\\([${CHINESE_NUM_CLASS}]+\\))(.*)$`,
  'u'
);
const SUBITEM_RE = /^(\d+(?:\.\d+)?[.\u3001])\s*(.*)$/u;
const STRUCTURED_LEVELS: HeadingLevel[] = ['chapter', 'section', 'article', 'item', 'subitem'];
const SPLIT_LEVELS = new Set<HeadingLevel>(['article', 'item', 'subitem']);

function fallbackMimeByName(fileName: string): string {
  const lower = fileName.toLowerCase();
  if (lower.endsWith('.txt')) return 'text/plain';
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return 'text/markdown';
  if (lower.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  if (lower.endsWith('.pdf')) return 'application/pdf';
  return 'application/octet-stream';
}

function normalizeMime(mime: string, fileName: string): string {
  const base = (mime || '').split(';')[0].trim().toLowerCase();
  if (!base || base === 'application/octet-stream') {
    return fallbackMimeByName(fileName);
  }
  if (base === 'text/x-markdown') return 'text/markdown';
  if (base === 'application/x-pdf') return 'application/pdf';
  return base;
}

function normalizeText(input: string): string {
  return input
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/\u0000/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function joinContent(lines: string[]): string {
  return lines
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function inferHeading(line: string): HeadingMatch | null {
  const value = line.trim();
  if (!value) return null;

  let matched = value.match(CHAPTER_RE);
  if (matched) {
    const suffix = (matched[2] || '').trim();
    return {
      level: 'chapter',
      segment: suffix ? `${matched[1]} ${suffix}` : matched[1],
      inlineBody: '',
      rawLine: value,
    };
  }

  matched = value.match(SECTION_RE);
  if (matched) {
    const suffix = (matched[2] || '').trim();
    return {
      level: 'section',
      segment: suffix ? `${matched[1]} ${suffix}` : matched[1],
      inlineBody: '',
      rawLine: value,
    };
  }

  matched = value.match(ARTICLE_RE);
  if (matched) {
    return {
      level: 'article',
      segment: matched[1],
      inlineBody: (matched[2] || '').trim(),
      rawLine: value,
    };
  }

  matched = value.match(ITEM_RE);
  if (matched) {
    return {
      level: 'item',
      segment: matched[1],
      inlineBody: (matched[2] || '').trim(),
      rawLine: value,
    };
  }

  matched = value.match(SUBITEM_RE);
  if (matched) {
    return {
      level: 'subitem',
      segment: matched[1].trim(),
      inlineBody: (matched[2] || '').trim(),
      rawLine: value,
    };
  }

  return null;
}

function levelIndex(level: HeadingLevel): number {
  return STRUCTURED_LEVELS.indexOf(level);
}

function setHeadingContext(context: Partial<Record<HeadingLevel, string>>, heading: HeadingMatch): string[] {
  const currentIndex = levelIndex(heading.level);
  STRUCTURED_LEVELS.forEach((level, index) => {
    if (index > currentIndex) {
      delete context[level];
    }
  });
  context[heading.level] = heading.segment;
  return STRUCTURED_LEVELS.map((level) => context[level]).filter((value): value is string => Boolean(value));
}

function buildFieldPath(headingPath: string[], fallback: string): string {
  return headingPath.length ? headingPath.join('/') : fallback;
}

function sharedHeadingPrefixLength(left: string[], right: string[]): number {
  const limit = Math.min(left.length, right.length);
  let index = 0;
  while (index < limit && left[index] === right[index]) {
    index += 1;
  }
  return index;
}

function isAncestorHeadingPath(parent: string[], child: string[]): boolean {
  if (parent.length >= child.length) return false;
  return parent.every((item, index) => child[index] === item);
}

function getParentHeadingPath(chunk: DraftChunk): string[] {
  return chunk.heading_path.slice(0, -1);
}

function hasSameParentHeadingPath(left: DraftChunk, right: DraftChunk): boolean {
  const leftParent = getParentHeadingPath(left);
  const rightParent = getParentHeadingPath(right);
  return leftParent.length === rightParent.length && leftParent.every((item, index) => rightParent[index] === item);
}

function isContentPrefixedByHeading(content: string, heading: string): boolean {
  const normalizedContent = content.trim();
  const normalizedHeading = heading.trim();
  return normalizedHeading.length > 0 && normalizedContent.startsWith(normalizedHeading);
}

function buildMergedContent(current: DraftChunk, next: DraftChunk): string {
  const prefixLength = sharedHeadingPrefixLength(current.heading_path, next.heading_path);
  const currentHeadings = current.heading_path.slice(prefixLength);
  const nextHeadings = next.heading_path.slice(prefixLength);
  if (currentHeadings.length === 0 && current.split_level !== 'paragraph' && current.heading_path.length > 0) {
    currentHeadings.push(current.heading_path[current.heading_path.length - 1]);
  }
  const currentPrefix = currentHeadings.filter((heading) => !isContentPrefixedByHeading(current.content, heading));
  const nextPrefix = nextHeadings.filter((heading) => !isContentPrefixedByHeading(next.content, heading));
  return joinContent([...currentPrefix, current.content, ...nextPrefix, next.content]);
}

function buildPreviewContent(chunk: DraftChunk): string {
  if (chunk.split_level === 'paragraph' || chunk.heading_path.length === 0) {
    return chunk.content;
  }
  const ownHeading = chunk.heading_path[chunk.heading_path.length - 1];
  if (isContentPrefixedByHeading(chunk.content, ownHeading)) {
    return chunk.content;
  }
  return joinContent([ownHeading, chunk.content]);
}

export function deriveHeadingPath(fieldPath: string): string[] {
  const normalized = String(fieldPath || '').trim();
  if (!normalized) return [];
  const segments = normalized.split('/').map((item) => item.trim()).filter((item) => item.length > 0);
  if (segments.length === 2 && /^(section|paragraph)$/i.test(segments[0]) && /^\d+$/.test(segments[1])) {
    return [normalized];
  }
  return segments.length ? segments : [normalized];
}

export function buildEmbeddingText(title: string, fieldPath: string, content: string): string {
  return [title.trim(), fieldPath.trim(), content.trim()].filter((item) => item.length > 0).join('\n');
}

function mergeShortChunksForward(chunks: DraftChunk[], minChars: number): DraftChunk[] {
  if (chunks.length <= 1) return chunks.filter((item) => item.content.trim().length > 0);

  const merged = chunks.map((item) => ({
    heading_path: [...item.heading_path],
    content: item.content.trim(),
    split_level: item.split_level,
  }));

  for (let index = 0; index < merged.length; index += 1) {
    const current = merged[index];
    if (!current || !current.content) continue;
    if (
      current.content.length >= minChars ||
      current.split_level === 'item' ||
      current.split_level === 'subitem' ||
      (current.split_level !== 'paragraph' && current.split_level !== 'article')
    ) {
      continue;
    }
    const next = merged[index + 1];
    const previous = [...merged].slice(0, index).reverse().find((item) => item.content);
    const following = merged[index + 2];
    const nextHasChild =
      next &&
      current.split_level === 'article' &&
      next.split_level === 'article' &&
      following &&
      isAncestorHeadingPath(next.heading_path, following.heading_path);
    const canMergeForward =
      Boolean(next?.content) &&
      ((current.split_level === 'paragraph' && next?.split_level === 'paragraph') ||
        (current.split_level === 'article' &&
          next?.split_level !== 'paragraph' &&
          !nextHasChild &&
          (hasSameParentHeadingPath(current, next) || isAncestorHeadingPath(current.heading_path, next.heading_path))));

    if (canMergeForward && next) {
      const currentIsParentOfNext = isAncestorHeadingPath(current.heading_path, next.heading_path);
      next.content = buildMergedContent(current, next);
      next.heading_path = [...current.heading_path];
      next.split_level = currentIsParentOfNext ? next.split_level : current.split_level;
      current.content = '';
      continue;
    }

    if (!previous) continue;
    if (current.split_level === 'paragraph' && previous.split_level !== 'paragraph') continue;
    previous.content = buildMergedContent(previous, current);
    current.content = '';
  }

  return merged.filter((item) => item.content.length > 0);
}

function splitStructured(text: string): { chunks: DraftChunk[]; splitCount: number } {
  const lines = text.split('\n');
  const context: Partial<Record<HeadingLevel, string>> = {};
  const chunks: DraftChunk[] = [];
  let splitCount = 0;
  let currentHeadingPath: string[] = [];
  let bodyLines: string[] = [];
  let currentSplitLevel: HeadingLevel | 'paragraph' = 'paragraph';

  const flush = () => {
    const content = joinContent(bodyLines);
    if (content) {
      chunks.push({
        heading_path: currentHeadingPath.length ? [...currentHeadingPath] : [],
        content,
        split_level: currentSplitLevel,
      });
    }
    bodyLines = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (bodyLines.length) {
        bodyLines.push('');
      }
      continue;
    }

    const heading = inferHeading(line);
    if (!heading) {
      if (!currentHeadingPath.length) {
        currentHeadingPath = STRUCTURED_LEVELS.map((level) => context[level]).filter((value): value is string => Boolean(value));
        currentSplitLevel = 'paragraph';
      }
      bodyLines.push(line);
      continue;
    }

    const nextHeadingPath = setHeadingContext(context, heading);
    if (SPLIT_LEVELS.has(heading.level)) {
      flush();
      currentHeadingPath = [...nextHeadingPath];
      currentSplitLevel = heading.level;
      splitCount += 1;
      if (heading.inlineBody) {
        bodyLines.push(heading.inlineBody);
      }
      continue;
    }

    flush();
    currentHeadingPath = [...nextHeadingPath];
    currentSplitLevel = 'paragraph';
  }

  flush();
  return { chunks, splitCount };
}

function splitByParagraph(text: string): DraftChunk[] {
  const blocks = text
    .split(/\n{2,}/g)
    .map((block) => block.trim())
    .filter((block) => block.length > 0);

  const context: Partial<Record<HeadingLevel, string>> = {};
  const chunks: DraftChunk[] = [];
  let fallbackIndex = 0;

  for (const block of blocks) {
    const lines = block.split('\n').map((line) => line.trim()).filter((line) => line.length > 0);
    const bodyLines: string[] = [];
    let headingPath = STRUCTURED_LEVELS.map((level) => context[level]).filter((value): value is string => Boolean(value));

    for (const line of lines) {
      const heading = inferHeading(line);
      if (!heading) {
        bodyLines.push(line);
        continue;
      }

      headingPath = setHeadingContext(context, heading);
      if (heading.inlineBody) {
        bodyLines.push(heading.inlineBody);
      }
    }

    const content = joinContent(bodyLines);
    if (!content) continue;
    fallbackIndex += 1;
    chunks.push({
      heading_path: headingPath,
      content,
      split_level: 'paragraph',
    });
  }

  return chunks.map((chunk, index) => ({
    heading_path: chunk.heading_path.length ? chunk.heading_path : [`paragraph/${index + 1}`],
    content: chunk.content,
    split_level: 'paragraph',
  }));
}

function groupParagraphChunks(chunks: DraftChunk[], minChars: number, maxChars: number): DraftChunk[] {
  const grouped: DraftChunk[] = [];
  let current: DraftChunk | null = null;

  const flush = () => {
    if (!current) return;
      grouped.push({
        heading_path: [...current.heading_path],
        content: current.content.trim(),
        split_level: 'paragraph',
      });
    current = null;
  };

  for (const chunk of chunks) {
    if (!current) {
      current = {
        heading_path: [...chunk.heading_path],
        content: chunk.content.trim(),
        split_level: 'paragraph',
      };
      continue;
    }

    const sameHeading = current.heading_path.join('/') === chunk.heading_path.join('/');
    const merged = joinContent([current.content, chunk.content]);
    if ((sameHeading && current.content.length < minChars) || merged.length <= maxChars) {
      current.content = merged;
      if (!current.heading_path.length && chunk.heading_path.length) {
        current.heading_path = [...chunk.heading_path];
      }
      continue;
    }

    flush();
    current = {
      heading_path: [...chunk.heading_path],
      content: chunk.content.trim(),
      split_level: 'paragraph',
    };
  }

  flush();
  return grouped;
}

function isPdfOcrRequired(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'PDF_OCR_REQUIRED';
}

async function extractPdfText(input: ParseDocumentInput): Promise<ExtractTextResult> {
  try {
    const parsed = await pdfParse(input.content);
    const text = parsed.text ?? '';
    if (text.trim().length < 20) {
      throw new ApiError(422, 'PDF_OCR_REQUIRED', 'PDF has no extractable text layer');
    }
    return { text, warnings: [] };
  } catch (error) {
    if (!isPdfOcrRequired(error)) {
      const ocrResult = await parseDocumentWithOcr({
        fileName: input.file_name,
        content: input.content,
      });
      return {
        text: ocrResult.text,
        warnings: ['PDF_TEXT_PARSE_FAILED', ...ocrResult.warnings],
      };
    }

    const ocrResult = await parseDocumentWithOcr({
      fileName: input.file_name,
      content: input.content,
    });
    return {
      text: ocrResult.text,
      warnings: ocrResult.warnings,
    };
  }
}

async function extractText(input: ParseDocumentInput): Promise<ExtractTextResult> {
  const mime = normalizeMime(input.file_mime, input.file_name);
  if (!SUPPORTED_FILE_TYPES.has(mime)) {
    throw new ApiError(400, 'UNSUPPORTED_FILE_TYPE', 'Only TXT/MD/DOCX/PDF are supported');
  }

  if (mime === 'text/plain' || mime === 'text/markdown') {
    return { text: input.content.toString('utf8'), warnings: [] };
  }

  if (mime === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
    const result = await mammoth.extractRawText({ buffer: input.content });
    return { text: result.value, warnings: [] };
  }

  return extractPdfText(input);
}

export async function parseDocumentForPreview(input: ParseDocumentInput): Promise<ParsePreviewResult> {
  const warnings: string[] = [];
  const minChars = Math.max(40, Math.floor(input.split_options?.min_clause_chars ?? 120));
  const maxChars = Math.max(minChars + 40, Math.floor(input.split_options?.max_clause_chars ?? 1200));
  const extracted = await extractText(input);
  warnings.push(...extracted.warnings);
  const rawText = extracted.text;
  const text = normalizeText(rawText);
  if (!text) {
    throw new ApiError(400, 'EMPTY_DOCUMENT', 'Document contains no readable text');
  }

  const structured = splitStructured(text);
  let chunks = mergeShortChunksForward(structured.chunks, minChars);
  const shouldFallback = structured.splitCount === 0 || chunks.length === 0;

  if (shouldFallback) {
    const paragraphChunks = groupParagraphChunks(splitByParagraph(text), minChars, maxChars);
    chunks = mergeShortChunksForward(paragraphChunks, minChars);
    warnings.push('AUTO_SPLIT_FALLBACK_PARAGRAPH');
  }

  if (!chunks.length) {
    throw new ApiError(400, 'EMPTY_DOCUMENT', 'Document contains no readable clauses');
  }

  return {
    warnings,
    clauses: chunks.map((chunk, index) => ({
      field_path: buildFieldPath(chunk.heading_path, `paragraph/${index + 1}`),
      heading_path: chunk.heading_path.length ? chunk.heading_path : [`paragraph/${index + 1}`],
      content: buildPreviewContent(chunk),
      tags: [],
    })),
  };
}
