import {
  buildAbTestMetadata,
  hasAbTestMetadata,
  withAbTestMetadata,
} from './metadata';
import {
  resolveSessionAbTestResolution,
  shouldEnableVehicleExpertDeepCot,
} from './service';
import type { AbTestResolution } from './types';
import type {
  ChatExperimentAdapter,
  ChatTurnContext,
  ChatTurnMetadataDetails,
} from '../chat/turn-context';
import { DEFAULT_RULE_ROUTING_MODE } from '../chat/turn-context';
import type { WorkerRuntimeOptions } from '../chat/worker-runner';

function readResolutionFromTurnContext(turnContext: ChatTurnContext): AbTestResolution | null {
  const value = turnContext.variantContext;
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const record = value as Partial<AbTestResolution>;
  if (typeof record.experiment !== 'string' || typeof record.source !== 'string') {
    return null;
  }
  return record as AbTestResolution;
}

function decorateWithAbMetadata(
  turnContext: ChatTurnContext,
  metadata: Record<string, unknown> | undefined,
  details?: ChatTurnMetadataDetails
): Record<string, unknown> {
  const resolution = readResolutionFromTurnContext(turnContext);
  if (!resolution) {
    return { ...(metadata ?? {}) };
  }
  return withAbTestMetadata(metadata, buildAbTestMetadata(resolution, details));
}

export function createNoopChatExperimentAdapter(): ChatExperimentAdapter {
  return {
    async createTurnContext() {
      return {
        routingMode: DEFAULT_RULE_ROUTING_MODE,
        variantContext: null,
      };
    },
    decorateAssistantMetadata(_turnContext, metadata) {
      return { ...(metadata ?? {}) };
    },
    decorateRouteMetadata(_turnContext, metadata) {
      return { ...metadata };
    },
    hasDecoratedAssistantMetadata() {
      return false;
    },
    resolveWorkerRuntimeOptions() {
      return undefined;
    },
  };
}

export function createAbChatExperimentAdapter(options: {
  driverExpertCotSystemPrompt?: string;
  vehicleExpertCotSystemPrompt: string;
}): ChatExperimentAdapter {
  return {
    async createTurnContext(db, sessionId) {
      const resolution = await resolveSessionAbTestResolution(db as any, sessionId);
      return {
        routingMode: resolution.routingMode,
        variantContext: resolution,
      };
    },
    decorateAssistantMetadata(turnContext, metadata, details) {
      return decorateWithAbMetadata(turnContext, metadata, details);
    },
    decorateRouteMetadata(turnContext, metadata, details) {
      return decorateWithAbMetadata(turnContext, metadata, details);
    },
    hasDecoratedAssistantMetadata(metadata) {
      return hasAbTestMetadata(metadata);
    },
    resolveWorkerRuntimeOptions(turnContext, params): WorkerRuntimeOptions | undefined {
      if (params.workerTool === 'consult_driver_expert') {
        return params.cotMode === 'deep' && options.driverExpertCotSystemPrompt
          ? { systemPromptPrefix: options.driverExpertCotSystemPrompt }
          : undefined;
      }
      const resolution = readResolutionFromTurnContext(turnContext);
      if (!shouldEnableVehicleExpertDeepCot(resolution, params.cotMode)) {
        return undefined;
      }
      return {
        systemPromptPrefix: options.vehicleExpertCotSystemPrompt,
      };
    },
  };
}
