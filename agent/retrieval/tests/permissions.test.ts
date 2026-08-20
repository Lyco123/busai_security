import { describe, expect, it } from 'vitest';
import { ensureCanWriteLevel, ensureDocumentVisibleOr404, ensureWritableContext } from '../src/permissions';
import type { CallerContext } from '../src/models/contracts';
import { ApiError } from '../src/utils/errors';
import { levelToRank } from '../src/models/access';

function buildCaller(level: 'driver' | 'fleet' | 'company' | 'group'): CallerContext {
  return {
    tenant_id: 't1',
    caller_level: level,
    caller_rank: levelToRank(level),
    caller_id: `u-${level}`,
    caller_company_id: level === 'company' ? 'c1' : undefined,
    request_id: 'req-1',
  };
}

describe('permission matrix', () => {
  it('driver and fleet are read only', () => {
    expect(() => ensureWritableContext(buildCaller('driver'))).toThrow(ApiError);
    expect(() => ensureWritableContext(buildCaller('fleet'))).toThrow(ApiError);
  });

  it('company can write up to company level', () => {
    const company = buildCaller('company');
    expect(() => ensureCanWriteLevel(company, 'driver')).not.toThrow();
    expect(() => ensureCanWriteLevel(company, 'fleet')).not.toThrow();
    expect(() => ensureCanWriteLevel(company, 'company')).not.toThrow();
    expect(() => ensureCanWriteLevel(company, 'group')).toThrow(ApiError);
  });

  it('group can write all levels', () => {
    const group = buildCaller('group');
    expect(() => ensureCanWriteLevel(group, 'driver')).not.toThrow();
    expect(() => ensureCanWriteLevel(group, 'fleet')).not.toThrow();
    expect(() => ensureCanWriteLevel(group, 'company')).not.toThrow();
    expect(() => ensureCanWriteLevel(group, 'group')).not.toThrow();
  });

  it('returns 404 for invisible document rank', () => {
    const company = buildCaller('company');
    expect(() => ensureDocumentVisibleOr404(company, levelToRank('group'))).toThrow(ApiError);
    expect(() => ensureDocumentVisibleOr404(company, levelToRank('company'))).not.toThrow();
  });
});
