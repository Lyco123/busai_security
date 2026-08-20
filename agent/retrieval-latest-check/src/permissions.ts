import type { AccessLevel } from './models/access';
import { levelToRank } from './models/access';
import type { CallerContext } from './models/contracts';
import { ApiError } from './utils/errors';

const COMPANY_RANK = levelToRank('company');

export function ensureWritableContext(caller: CallerContext): void {
  if (caller.caller_rank < COMPANY_RANK) {
    throw new ApiError(403, 'WRITE_FORBIDDEN', 'Current caller level has no write permissions');
  }
  if (caller.caller_level === 'company' && !caller.caller_company_id) {
    throw new ApiError(403, 'MISSING_CALLER_COMPANY', 'Company level write requires X-Caller-Company-Id');
  }
}

export function ensureCanWriteLevel(caller: CallerContext, targetLevel: AccessLevel): void {
  ensureWritableContext(caller);
  const targetRank = levelToRank(targetLevel);
  if (caller.caller_rank < targetRank) {
    throw new ApiError(403, 'WRITE_LEVEL_FORBIDDEN', `Caller cannot write ${targetLevel} level resources`);
  }
}

export function ensureCanReadLevel(caller: CallerContext, targetRank: number): boolean {
  return caller.caller_rank >= targetRank;
}

export function ensureDocumentVisibleOr404(caller: CallerContext, targetRank: number): void {
  if (!ensureCanReadLevel(caller, targetRank)) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
}
