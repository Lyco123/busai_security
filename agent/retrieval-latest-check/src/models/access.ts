export type AccessLevel = 'driver' | 'fleet' | 'company' | 'group';

export const ACCESS_RANK: Record<AccessLevel, number> = {
  driver: 10,
  fleet: 20,
  company: 30,
  group: 40,
};

export function isAccessLevel(value: string): value is AccessLevel {
  return value === 'driver' || value === 'fleet' || value === 'company' || value === 'group';
}

export function levelToRank(level: AccessLevel): number {
  return ACCESS_RANK[level];
}
