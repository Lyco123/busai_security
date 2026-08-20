import type { RuleRoutingMode } from './turn-context';

export interface RuleMatchItemForPrompt {
  rule_id?: string;
  rule_name?: string;
  score?: number;
  metadata?: { match_text?: string; tone?: string };
}

export interface RuleMatchContextForPrompt {
  ok: boolean;
  matches: RuleMatchItemForPrompt[];
  error?: string;
}

export const ROUTER_SKILL_RUNTIME_SUPPLEMENT = [
  '## 运行时上下文使用',
  '- 系统可能额外注入 `PENDING FURTHER INFO CONTEXT` 或 `LATEST STRUCTURED REPORT CONTEXT`。',
  '- 这些上下文首先用于判断当前轮是在继续上一轮澄清或报告追问，还是已经切换成新的请求。',
  '- 一旦确认当前轮是在继续同一任务，可以结合这些上下文恢复最近多轮里分散提供的缺失信息、目标对象或补充参数。',
  '- 不要让运行时上下文覆盖 router skill 主体规则、报告与咨询的边界，或工具描述中的主定义。',
  '- 如果当前轮明确改变了话题、对象或任务类型，应忽略旧上下文，按当前轮重新路由。',
].join('\n');

function renderRuleRoutingPolicyForPrompt(
  routingMode: RuleRoutingMode,
  skipRuleId?: string
): string {
  const lines = ['[RULE_ROUTING_POLICY]', `mode: ${routingMode}`];
  lines.push('rule: 当前策略固定为 router_decide。');
  lines.push(
    'rule: 当 top1 score >= threshold 时，规则命中是强证据，但不是默认命令；仍需结合当前用户意图、请求类型和规则适用范围判断 rule_reply 是否合适。'
  );
  lines.push(
    'rule: 一旦决定调用 rule_reply，不要输出额外自然语言解释，也不要把工具调用文本直接展示给用户。'
  );
  if (skipRuleId) {
    lines.push(`guard: 本轮不要再次调用 rule_id 为 "${skipRuleId}" 的 rule_reply。`);
  }
  return lines.join('\n');
}

export function renderRuleMatchForPrompt(
  ruleMatch: RuleMatchContextForPrompt,
  routingMode: RuleRoutingMode,
  skipRuleId?: string,
  ruleMatchThreshold = 0.7
): string {
  const header = '[RULE_MATCH_RESULTS]';
  const policy = renderRuleRoutingPolicyForPrompt(routingMode, skipRuleId);
  if (!ruleMatch.ok) {
    return `${policy}\n\n${header}\nstatus: unavailable (${ruleMatch.error ?? 'match_rules_failed'})\naction: 规则匹配不可用，继续按 router skill 与工具描述做正常路由。`;
  }
  if (!ruleMatch.matches.length) {
    return `${policy}\n\n${header}\nstatus: none\naction: 当前没有命中规则，继续按 router skill 与工具描述做正常路由。本轮禁止调用 rule_reply。`;
  }

  const primaryMatch = ruleMatch.matches[0];
  const effectiveTopMatch =
    skipRuleId && primaryMatch?.rule_id === skipRuleId
      ? (ruleMatch.matches.find((item) => item.rule_id && item.rule_id !== skipRuleId) ??
        primaryMatch)
      : primaryMatch;
  const topScore = typeof effectiveTopMatch?.score === 'number' ? effectiveTopMatch.score : 0;
  const topRuleId = typeof effectiveTopMatch?.rule_id === 'string' ? effectiveTopMatch.rule_id : '';
  const display = ruleMatch.matches.map((item) => ({
    rule_id: item.rule_id,
    rule_name: item.rule_name,
    score: typeof item.score === 'number' ? Number(item.score.toFixed(3)) : item.score,
    metadata: item.metadata,
  }));

  const lines = [policy, '', header, JSON.stringify(display, null, 2)];
  if (skipRuleId && primaryMatch?.rule_id === skipRuleId) {
    if (effectiveTopMatch?.rule_id && effectiveTopMatch.rule_id !== skipRuleId) {
      lines.push(
        `note: 本轮 top1 的 rule_id "${skipRuleId}" 已被禁止，请评估下一候选规则 "${effectiveTopMatch.rule_id}"。`
      );
    } else {
      lines.push(`note: 本轮 top1 的 rule_id "${skipRuleId}" 已被禁止，且没有可替代规则。`);
    }
  }

  if (topScore >= ruleMatchThreshold) {
    if (skipRuleId && topRuleId && topRuleId === skipRuleId) {
      lines.push(
        `top1 score ${topScore.toFixed(3)} >= threshold ${ruleMatchThreshold}，但该规则被 guard 禁止 -> 不要再次调用它，继续评估其他规则或常规路由。`
      );
    } else if (topRuleId) {
      lines.push(
        `top1 score ${topScore.toFixed(3)} >= threshold ${ruleMatchThreshold} -> 这是强规则证据，但不代表必须或默认优先走 rule_reply；请结合当前请求意图与规则适用范围，评估 rule_reply(user_query, rule_id="${topRuleId}", hit_rules=the list above) 是否合适。`
      );
    } else {
      lines.push(
        `top1 score ${topScore.toFixed(3)} >= threshold ${ruleMatchThreshold} -> 这是强规则证据，但不代表必须或默认优先走 rule_reply；请结合当前请求意图与规则适用范围，评估 rule_reply(user_query, hit_rules=the list above) 是否合适。`
      );
    }
  } else {
    lines.push(`status: top1 score ${topScore.toFixed(3)} < threshold ${ruleMatchThreshold}`);
    lines.push(
      'action: 分数低于阈值，继续按 router skill 与工具描述做正常路由；但如果表达与规则名称、match_text、examples 或上一轮同话题高度一致，不要草率退回泛化回答。'
    );
  }

  return lines.join('\n');
}
