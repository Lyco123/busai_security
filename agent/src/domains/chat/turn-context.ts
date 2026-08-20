import type { WorkerRuntimeOptions } from './worker-runner';

export type RuleRoutingMode = 'router_decide';

export const DEFAULT_RULE_ROUTING_MODE: RuleRoutingMode = 'router_decide';

export interface ChatTurnContext {
  routingMode: RuleRoutingMode;
  variantContext: unknown | null;
}

export interface ChatTurnMetadataDetails {
  selectedTool?: string | null;
  selectedRuleId?: string | null;
  topScore?: number;
  ruleExitFallback?: boolean;
  skipRuleId?: string | null;
}

export interface ResolveWorkerRuntimeOptionsParams {
  workerTool: string;
  cotMode?: string | null;
  historyMessages: Array<{ role: string; content: string }>;
  userQuery: string;
}

export interface ChatExperimentAdapter {
  createTurnContext(db: unknown, sessionId: string): Promise<ChatTurnContext>;
  decorateAssistantMetadata(
    turnContext: ChatTurnContext,
    metadata: Record<string, unknown> | undefined,
    details?: ChatTurnMetadataDetails
  ): Record<string, unknown>;
  decorateRouteMetadata(
    turnContext: ChatTurnContext,
    metadata: Record<string, unknown>,
    details?: ChatTurnMetadataDetails
  ): Record<string, unknown>;
  hasDecoratedAssistantMetadata(metadata: unknown): boolean;
  resolveWorkerRuntimeOptions?(
    turnContext: ChatTurnContext,
    params: ResolveWorkerRuntimeOptionsParams
  ): WorkerRuntimeOptions | undefined;
}
