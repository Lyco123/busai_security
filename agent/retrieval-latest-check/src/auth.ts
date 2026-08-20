import type { FastifyRequest } from 'fastify';
import { isAccessLevel, levelToRank } from './models/access';
import type { CallerContext } from './models/contracts';
import { ApiError } from './utils/errors';
import { newId } from './utils/id';

function readHeader(request: FastifyRequest, key: string): string {
  const raw = request.headers[key.toLowerCase()];
  if (Array.isArray(raw)) {
    return raw[0] ?? '';
  }
  if (typeof raw === 'string') {
    return raw.trim();
  }
  return '';
}

export function resolveCallerContext(request: FastifyRequest): CallerContext {
  const tenantId = readHeader(request, 'x-tenant-id');
  const callerLevelRaw = readHeader(request, 'x-caller-level');
  const callerId = readHeader(request, 'x-caller-id');
  const callerCompanyId = readHeader(request, 'x-caller-company-id');
  const requestId = readHeader(request, 'x-request-id') || newId('req');

  if (!tenantId) {
    throw new ApiError(400, 'MISSING_TENANT_ID', 'Header X-Tenant-Id is required');
  }
  if (!callerLevelRaw || !isAccessLevel(callerLevelRaw)) {
    throw new ApiError(400, 'INVALID_CALLER_LEVEL', 'Header X-Caller-Level is required and must be driver/fleet/company/group');
  }
  if (!callerId) {
    throw new ApiError(400, 'MISSING_CALLER_ID', 'Header X-Caller-Id is required');
  }

  return {
    tenant_id: tenantId,
    caller_level: callerLevelRaw,
    caller_rank: levelToRank(callerLevelRaw),
    caller_id: callerId,
    caller_company_id: callerCompanyId || undefined,
    request_id: requestId,
  };
}
