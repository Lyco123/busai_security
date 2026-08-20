const GUANGDONG_PLATE_PREFIXES = new Set(['A', 'E']);

function compactVehiclePlateToken(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .toUpperCase()
    .replace(/[\s"'`.,，。:：;；()（）[\]【】{}<>《》-]/g, '');
}

export function normalizeGuangdongVehiclePlate(value: unknown): string {
  if (typeof value !== 'string') {
    return '';
  }

  const compact = compactVehiclePlateToken(value);

  if (!compact) {
    return '';
  }

  const withoutProvince = compact.startsWith('粤') ? compact.slice(1) : compact;
  const prefix = withoutProvince.slice(0, 1);
  const body = withoutProvince.slice(1);

  if (GUANGDONG_PLATE_PREFIXES.has(prefix) && /^[A-Z0-9]{4,7}$/.test(body)) {
    return `粤${prefix}${body}`;
  }

  return compact;
}

export function isMissingGuangdongVehiclePlateSeries(value: unknown): boolean {
  if (typeof value !== 'string') {
    return false;
  }

  const compact = compactVehiclePlateToken(value);
  if (!compact || compact.startsWith('粤')) {
    return false;
  }

  if (GUANGDONG_PLATE_PREFIXES.has(compact.slice(0, 1))) {
    return false;
  }

  return /^(?=.*\d)[A-Z0-9]{5,7}$/.test(compact);
}

export function normalizeVehiclePlateArg<T extends Record<string, unknown>>(
  args: T,
  key: keyof T
): T {
  const current = args[key];
  const normalized = normalizeGuangdongVehiclePlate(current);
  if (!normalized || normalized === current) {
    return args;
  }
  return { ...args, [key]: normalized };
}
