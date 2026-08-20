export type ProfileQuotaTreeItem = {
  quotaId: string | null;
  quotaName: string;
  quotaLevel: string | null;
  parentId: string | null;
  firstQuotaName?: string | null;
  score?: number | null;
  originalValue?: number | null;
  ranking?: number | null;
};

export type ProfileQuotaRootConfig<TDimension extends string = string> = {
  rootId: string;
  dimension: TDimension;
};

// TODO(ai-security-mcp-score-hotfix): Remove these compatibility aliases once the
// MCP schema/description names score and originalValue with their real semantics.
export const PROFILE_RISK_SCORE_SEMANTICS =
  '画像类 final_risk_score/originalValue 为最终风险分或最终风险贡献，数值越高表示风险越高、越突出，不代表安全分。';

export const PROFILE_SOURCE_SCORE_SEMANTICS =
  '上游画像指标字段 score 不是最终分数，仅作为源指标分/计算中间值保留；生成报告和解释指标贡献时优先使用 final_risk_score/originalValue。';

export const PROFILE_SUGGESTION_SCORE_SEMANTICS =
  '建议明细类 score 为风险建议分/风险优先级分，数值越高表示风险越高、越需要优先关注，不代表安全分。';

export const PROFILE_WEIGHTED_VALUE_SEMANTICS =
  '画像指标 originalValue 是最终风险分/最终风险贡献，通常接近上游 score * weightRate；不应解释为原始行为次数。';

export const PROFILE_COUNT_SEMANTICS =
  '只有原始业务字段明确返回次数/条数/起数时才可解释为 count；不得由 score 或 originalValue 推断次数。';

export function resolveProfileFinalRiskScore(
  item: Pick<ProfileQuotaTreeItem, 'score' | 'originalValue'>
): number | null {
  // TODO(ai-security-mcp-score-hotfix): Delete this fallback when upstream exposes
  // the final risk score with an unambiguous field name.
  return item.originalValue ?? item.score ?? null;
}

export function normalizeQuotaTreeCount(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value) || value <= 0) return null;
  if (Math.abs(value - Math.round(value)) > 0.000001) return null;
  return Math.round(value);
}

export function buildQuotaItemIndex<TItem extends ProfileQuotaTreeItem>(
  items: TItem[]
): Map<string, TItem> {
  const itemById = new Map<string, TItem>();
  for (const item of items) {
    if (item.quotaId) itemById.set(item.quotaId, item);
  }
  return itemById;
}

export function buildQuotaChildrenIndex<TItem extends ProfileQuotaTreeItem>(
  items: TItem[]
): Map<string, TItem[]> {
  const childrenByParent = new Map<string, TItem[]>();
  for (const item of items) {
    if (!item.parentId) continue;
    const bucket = childrenByParent.get(item.parentId) ?? [];
    bucket.push(item);
    childrenByParent.set(item.parentId, bucket);
  }
  return childrenByParent;
}

export function isLeafQuotaTreeItem<TItem extends ProfileQuotaTreeItem>(
  item: TItem,
  childrenByParent: Map<string, TItem[]>
): boolean {
  if (item.quotaLevel === '3') return true;
  if (!item.quotaId) return false;
  return !childrenByParent.has(item.quotaId);
}

export function isQuotaTreeDescendantOfRoot<TItem extends ProfileQuotaTreeItem>(
  item: TItem,
  rootId: string,
  itemById: Map<string, TItem>
): boolean {
  if (!item.quotaId || item.quotaId === rootId || item.quotaLevel === '1') {
    return false;
  }

  let current: TItem | undefined = item;
  const visited = new Set<string>();
  while (current) {
    if (current.parentId === rootId) return true;
    if (!current.parentId || visited.has(current.parentId)) break;
    visited.add(current.parentId);
    current = itemById.get(current.parentId);
  }

  return false;
}

export function pickTopLeafQuotaItemsByRoot<TItem extends ProfileQuotaTreeItem>(
  items: TItem[],
  rootId: string,
  limit: number
): TItem[] {
  const itemById = buildQuotaItemIndex(items);
  const childrenByParent = buildQuotaChildrenIndex(items);
  return items
    .filter((item) => resolveProfileFinalRiskScore(item) != null)
    .filter((item) => isQuotaTreeDescendantOfRoot(item, rootId, itemById))
    .filter((item) => isLeafQuotaTreeItem(item, childrenByParent))
    .sort((left, right) => {
      const scoreDelta =
        (resolveProfileFinalRiskScore(right) ?? Number.NEGATIVE_INFINITY) -
        (resolveProfileFinalRiskScore(left) ?? Number.NEGATIVE_INFINITY);
      if (scoreDelta !== 0) return scoreDelta;
      return (right.score ?? Number.NEGATIVE_INFINITY) - (left.score ?? Number.NEGATIVE_INFINITY);
    })
    .filter(
      (item, index, array) =>
        array.findIndex((candidate) => candidate.quotaName === item.quotaName) === index
    )
    .slice(0, limit);
}

export function resolveQuotaDimensionByRoots<TItem extends ProfileQuotaTreeItem, TDimension extends string>(
  item: TItem,
  itemById: Map<string, TItem>,
  roots: readonly ProfileQuotaRootConfig<TDimension>[]
): TDimension | null {
  if (!item.quotaId) return null;

  const rootMap = new Map<string, TDimension>(roots.map((root) => [root.rootId, root.dimension]));
  let current: TItem | undefined = item;
  const visited = new Set<string>();
  while (current) {
    if (current.quotaId) {
      const matched = rootMap.get(current.quotaId);
      if (matched) return matched;
    }
    if (!current.parentId || visited.has(current.parentId)) break;
    visited.add(current.parentId);
    current = itemById.get(current.parentId);
  }

  return null;
}
