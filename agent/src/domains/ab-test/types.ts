import type { AbTestGroup } from './config';
import type { RuleRoutingMode } from '../chat/turn-context';

export type AbTestSource = 'session_bound' | 'assigned' | 'legacy';

export interface AbTestResolution {
  experiment: string;
  group: AbTestGroup | null;
  locked: boolean;
  source: AbTestSource;
  routingMode: RuleRoutingMode;
}

export interface AbTestMetadataDetails {
  selectedTool?: string | null;
  selectedRuleId?: string | null;
  topScore?: number;
  ruleExitFallback?: boolean;
  skipRuleId?: string | null;
}
