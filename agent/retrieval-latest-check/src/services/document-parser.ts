import mammoth from 'mammoth';
import pdfParse from 'pdf-parse';
import { ApiError } from '../utils/errors';

export interface ParsedClauseDraft {
  field_path: string;
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

const SUPPORTED_FILE_TYPES = new Set(['text/plain', 'text/markdown', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/pdf']);

const HEADING_RE = /^(第[一二三四五六七八九十百千万\d]+[条章节款]|[一二三四五六七八九十]+、|（[一二三四五六七八九十\d]+）|\d+(?:\.\d+)*[.、])\s*/u;

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

function splitByHeading(text: string): ParsedClauseDraft[] {
  const lines = text.split('\n').map((line) => line.trim()).filter((line) => line.length > 0);
  const clauses: string[] = [];
  let current = '';

  for (const line of lines) {
    if (HEADING_RE.test(line)) {
      if (current) clauses.push(current.trim());
      current = line;
      continue;
    }
    current = current ? `${current}\n${line}` : line;
  }
  if (current) clauses.push(current.trim());

  return clauses.map((content, index) => ({
    field_path: `section/${index + 1}`,
    content,
    tags: [],
  }));
}

function splitByParagraph(text: string, minChars: number, maxChars: number): ParsedClauseDraft[] {
  const paragraphs = text
    .split(/\n{2,}/g)
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);

  const chunks: string[] = [];
  let buffer = '';
  for (const paragraph of paragraphs) {
    const next = buffer ? `${buffer}\n\n${paragraph}` : paragraph;
    if (next.length > maxChars && buffer) {
      chunks.push(buffer.trim());
      buffer = paragraph;
      continue;
    }
    buffer = next;
    if (buffer.length >= minChars) {
      chunks.push(buffer.trim());
      buffer = '';
    }
  }
  if (buffer) {
    chunks.push(buffer.trim());
  }

  return chunks.map((content, index) => ({
    field_path: `paragraph/${index + 1}`,
    content,
    tags: [],
  }));
}

async function extractText(input: ParseDocumentInput): Promise<string> {
  const mime = normalizeMime(input.file_mime, input.file_name);
  if (!SUPPORTED_FILE_TYPES.has(mime)) {
    throw new ApiError(400, 'UNSUPPORTED_FILE_TYPE', 'Only TXT/MD/DOCX/PDF are supported');
  }

  if (mime === 'text/plain' || mime === 'text/markdown') {
    return input.content.toString('utf8');
  }

  if (mime === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
    const result = await mammoth.extractRawText({ buffer: input.content });
    return result.value;
  }

  try {
    const parsed = await pdfParse(input.content);
    const text = parsed.text ?? '';
    if (text.trim().length < 20) {
      throw new ApiError(422, 'PDF_OCR_REQUIRED', 'PDF has no extractable text layer');
    }
    return text;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(422, 'PDF_OCR_REQUIRED', 'PDF has no extractable text layer');
  }
}

export async function parseDocumentForPreview(input: ParseDocumentInput): Promise<ParsePreviewResult> {
  const warnings: string[] = [];
  const minChars = Math.max(40, Math.floor(input.split_options?.min_clause_chars ?? 120));
  const maxChars = Math.max(minChars + 40, Math.floor(input.split_options?.max_clause_chars ?? 1200));
  const rawText = await extractText(input);
  const text = normalizeText(rawText);
  if (!text) {
    throw new ApiError(400, 'EMPTY_DOCUMENT', 'Document contains no readable text');
  }

  let clauses = splitByHeading(text);
  const avgLength = clauses.length ? Math.floor(clauses.reduce((sum, item) => sum + item.content.length, 0) / clauses.length) : 0;
  if (clauses.length <= 1 || avgLength < minChars / 2) {
    clauses = splitByParagraph(text, minChars, maxChars);
    warnings.push('AUTO_SPLIT_FALLBACK_PARAGRAPH');
  }
  if (!clauses.length) {
    throw new ApiError(400, 'EMPTY_DOCUMENT', 'Document contains no readable clauses');
  }

  return {
    warnings,
    clauses,
  };
}
