import { config } from '../config';
import { ApiError } from '../utils/errors';

interface OcrPageResult {
  page: number;
  text: string;
  confidence: number;
}

interface OcrResponse {
  success: boolean;
  engine?: string;
  full_text?: string | null;
  pages?: OcrPageResult[] | null;
  elapsed_ms?: number;
  warnings?: string[];
  error_code?: string | null;
  message?: string | null;
}

function requireOcrEndpoint(): string {
  if (!config.ocrEnabled) {
    throw new ApiError(422, 'PDF_OCR_REQUIRED', 'PDF has no extractable text layer');
  }
  if (!config.ocrBaseUrl) {
    throw new ApiError(500, 'OCR_NOT_CONFIGURED', 'OCR is enabled but OCR_BASE_URL is empty');
  }
  return `${config.ocrBaseUrl.replace(/\/+$/u, '')}/ocr/parse`;
}

function mapOcrErrorCode(code: string | null | undefined): string {
  if (!code) return 'OCR_FAILED';
  return `OCR_${code}`;
}

export async function parseDocumentWithOcr(input: {
  fileName: string;
  content: Buffer;
}): Promise<{ text: string; warnings: string[] }> {
  const endpoint = requireOcrEndpoint();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.ocrTimeoutMs);

  try {
    const form = new FormData();
    const fileBytes = new Uint8Array(input.content);
    form.append('file', new Blob([fileBytes], { type: 'application/pdf' }), input.fileName);
    form.append('language', config.ocrLanguage);
    form.append('mode', 'standard');

    const response = await fetch(endpoint, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    });

    let payload: OcrResponse | null = null;
    try {
      payload = (await response.json()) as OcrResponse;
    } catch {
      payload = null;
    }

    if (!response.ok) {
      throw new ApiError(response.status, 'OCR_HTTP_ERROR', payload?.message || `OCR service returned ${response.status}`);
    }

    if (!payload?.success) {
      throw new ApiError(422, mapOcrErrorCode(payload?.error_code), payload?.message || 'OCR failed');
    }

    const text = String(payload.full_text || '').trim();
    if (!text) {
      throw new ApiError(422, 'OCR_EMPTY_TEXT', 'OCR service returned empty text');
    }

    return {
      text,
      warnings: ['PDF_OCR_APPLIED', ...(payload.warnings || []).filter(Boolean).map((item) => `OCR_WARNING:${item}`)],
    };
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(504, 'OCR_TIMEOUT', 'OCR request timed out');
    }
    throw new ApiError(502, 'OCR_REQUEST_FAILED', error instanceof Error ? error.message : 'OCR request failed');
  } finally {
    clearTimeout(timeout);
  }
}
