import { isRecord } from './guards';

export type MessageSource = Record<string, unknown> & {
  type: string;
  path: string;
  path_args?: Record<string, unknown>;
};

function normalizeSourceType(value: unknown): string {
  const normalized = typeof value === 'string' ? value.trim() : '';
  return normalized || 'mcp';
}

function normalizeSourcePath(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normalizeSourcePathArgs(value: unknown): Record<string, unknown> | undefined {
  if (!isRecord(value)) return undefined;
  return Object.keys(value).length > 0 ? value : undefined;
}

export function normalizeMessageSource(value: unknown): MessageSource | null {
  if (!isRecord(value)) return null;
  const path = normalizeSourcePath(value.path);
  if (!path) return null;
  const pathArgs = normalizeSourcePathArgs(value.path_args ?? value.pathArgs);
  return {
    type: normalizeSourceType(value.type),
    path,
    ...(pathArgs ? { path_args: pathArgs } : {}),
  };
}

export function normalizeMessageSources(value: unknown): MessageSource[] {
  if (!Array.isArray(value)) return [];
  return value.map(normalizeMessageSource).filter((item): item is MessageSource => Boolean(item));
}

function buildMessageSourceKey(source: MessageSource): string {
  return JSON.stringify({
    type: source.type,
    path: source.path,
    path_args: source.path_args ?? null,
  });
}

export function mergeMessageSources(
  base: MessageSource[],
  incoming: MessageSource[]
): MessageSource[] {
  const merged = [...base];
  const seen = new Set(merged.map(buildMessageSourceKey));
  for (const item of incoming) {
    const key = buildMessageSourceKey(item);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged;
}

function extractInlineSource(record: Record<string, unknown>, fallbackType?: string): MessageSource[] {
  const path = normalizeSourcePath(record.path);
  if (!path) return [];
  const pathArgs = normalizeSourcePathArgs(record.path_args ?? record.pathArgs);
  return [
    {
      type: normalizeSourceType(record.type ?? fallbackType),
      path,
      ...(pathArgs ? { path_args: pathArgs } : {}),
    },
  ];
}

export function extractMessageSources(value: unknown, fallbackType?: string): MessageSource[] {
  if (!isRecord(value)) return [];
  let collected = normalizeMessageSources(value.sources);
  collected = mergeMessageSources(collected, extractInlineSource(value, fallbackType));

  if (isRecord(value.result)) {
    collected = mergeMessageSources(collected, extractMessageSources(value.result, fallbackType));
  }
  if (isRecord(value.data)) {
    collected = mergeMessageSources(collected, extractMessageSources(value.data, fallbackType));
  }

  return collected;
}

export function withMessageSources<T extends Record<string, unknown>>(
  payload: T,
  sources: MessageSource[]
): T {
  if (!sources.length) return payload;
  const merged = mergeMessageSources(normalizeMessageSources(payload.sources), sources);
  return {
    ...payload,
    sources: merged,
  };
}

export function buildMcpDataSource(
  toolName: string,
  args?: Record<string, unknown>
): MessageSource {
  const pathArgs = normalizeSourcePathArgs(args);
  return {
    type: 'mcp_data_source',
    path: toolName,
    ...(pathArgs ? { path_args: pathArgs } : {}),
  };
}
