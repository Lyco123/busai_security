export type AbTestGroup = 'X' | 'Y';
export type RuleRoutingMode = 'router_decide';

export interface AbTestMetricContext {
  selectedTool: string;
}

export interface AbTestMetricDefinition {
  key: string;
  label: string;
  test: (context: AbTestMetricContext) => boolean;
}

export interface AbTestMetricSnapshot {
  key: string;
  label: string;
  values: Record<string, number>;
}

export interface AbTestStatsResponse {
  experiment: string;
  title: string;
  groups: string[];
  sample_turns: number;
  sample_sessions: number;
  metrics: AbTestMetricSnapshot[];
  updated_at: string;
}

export interface AbTestExperimentDefinition {
  id: string;
  title: string;
  groups: readonly AbTestGroup[];
  groupDisplayLabels: Record<AbTestGroup, string>;
  defaultGroup: AbTestGroup;
  routingMode: RuleRoutingMode;
  statsMetrics: readonly AbTestMetricDefinition[];
}

export const ACTIVE_AB_TEST_EXPERIMENT: AbTestExperimentDefinition = {
  id: 'vehicle_expert_cot',
  title: '车辆专家 CoT 开关统计',
  groups: ['X', 'Y'],
  groupDisplayLabels: {
    X: 'baseline',
    Y: 'cot_enabled',
  },
  defaultGroup: 'Y',
  routingMode: 'router_decide',
  statsMetrics: [
    {
      key: 'turns',
      label: '轮次',
      test: () => true,
    },
    {
      key: 'omni_selected',
      label: '`consult_omni` 选择',
      test: ({ selectedTool }) => selectedTool === 'consult_omni',
    },
    {
      key: 'vehicle_expert_selected',
      label: '车辆专家选择',
      test: ({ selectedTool }) => selectedTool === 'consult_vehicle_expert',
    },
    {
      key: 'rule_reply_selected',
      label: '`rule_reply` 选择',
      test: ({ selectedTool }) => selectedTool === 'rule_reply',
    },
    {
      key: 'report_selected',
      label: '报告链路选择',
      test: ({ selectedTool }) =>
        selectedTool === 'generate_driver_report' ||
        selectedTool === 'generate_vehicle_report' ||
        selectedTool === 'generate_unit_report' ||
        selectedTool === 'generate_route_report' ||
        selectedTool === 'generate_station_report' ||
        selectedTool === 'generate_accident_investigation_report',
    },
    {
      key: 'other_selected',
      label: '其他链路处理',
      test: ({ selectedTool }) =>
        Boolean(selectedTool) &&
        selectedTool !== 'consult_omni' &&
        selectedTool !== 'consult_vehicle_expert' &&
        selectedTool !== 'rule_reply' &&
        selectedTool !== 'generate_driver_report' &&
        selectedTool !== 'generate_vehicle_report' &&
        selectedTool !== 'generate_unit_report' &&
        selectedTool !== 'generate_route_report' &&
        selectedTool !== 'generate_station_report' &&
        selectedTool !== 'generate_accident_investigation_report',
    },
  ],
};

export function getAbTestGroupDisplayLabel(group: AbTestGroup): string {
  return ACTIVE_AB_TEST_EXPERIMENT.groupDisplayLabels[group] ?? group.toLowerCase();
}

export function getActiveAbTestDisplayGroups(): string[] {
  return ACTIVE_AB_TEST_EXPERIMENT.groups.map((group) => getAbTestGroupDisplayLabel(group));
}

export function createAbTestStatsBucket(groups: readonly string[]): Record<string, number> {
  return Object.fromEntries(groups.map((group) => [group, 0]));
}

export function isAbTestGroup(value: unknown): value is AbTestGroup {
  return value === 'X' || value === 'Y';
}
