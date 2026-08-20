import {
  buildInitialRuleFieldMeta as buildInitialRuleFieldMetaBase,
  buildRuleConfigMetadata,
  computeRuleConfigMissingFields,
  computeRuleConfigState,
  hasRuleConfigFieldValue,
  normalizeRuleConfigState,
  normalizeRuleReworkTicket,
  renderRuleConfigAssistantMessage,
  renderRuleConfigQuestionFromField,
  toRuleConfigFieldLabel,
} from './pure';

export {
  buildRuleConfigMetadata,
  computeRuleConfigMissingFields,
  computeRuleConfigState,
  hasRuleConfigFieldValue,
  normalizeRuleConfigState,
  normalizeRuleReworkTicket,
  renderRuleConfigAssistantMessage,
  renderRuleConfigQuestionFromField,
  toRuleConfigFieldLabel,
};

export function createRuleConfigStateMachine(createId: (prefix: string) => string) {
  return {
    buildInitialRuleFieldMeta(draft: Record<string, unknown>) {
      return buildInitialRuleFieldMetaBase(draft, createId);
    },
    buildRuleConfigMetadata,
    computeRuleConfigMissingFields,
    computeRuleConfigState,
    hasRuleConfigFieldValue,
    normalizeRuleConfigState,
    normalizeRuleReworkTicket,
    renderRuleConfigAssistantMessage,
    renderRuleConfigQuestionFromField,
    toRuleConfigFieldLabel,
  };
}
