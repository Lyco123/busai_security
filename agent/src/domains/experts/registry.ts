import {
  DRIVER_EXPERT_COT_SYSTEM_PROMPT,
  INCIDENT_EXPERT_COT_SYSTEM_PROMPT,
  ROUTE_EXPERT_COT_SYSTEM_PROMPT,
  UNIT_EXPERT_COT_SYSTEM_PROMPT,
  VEHICLE_EXPERT_COT_SYSTEM_PROMPT,
} from '../chat/vehicle-expert-prompts';
import type { WorkerToolName } from '../chat/worker-runner';

export type ExpertDomain = 'driver' | 'vehicle' | 'unit' | 'route' | 'station' | 'incident';
export type ExpertTaskType = 'consult' | 'report';

export interface ExpertContextFlags {
  profile?: boolean;
  kb?: boolean;
  latestReport?: boolean;
  pendingClarification?: boolean;
}

export interface ExpertRegistryItem {
  domain: ExpertDomain;
  taskType: ExpertTaskType;
  workerTool: WorkerToolName;
  skillKey: string;
  supportsDeepCot?: boolean;
  deepCotSystemPrompt?: string;
  contextFlags: ExpertContextFlags;
}

const EXPERT_REGISTRY: ExpertRegistryItem[] = [
  {
    domain: 'driver',
    taskType: 'consult',
    workerTool: 'consult_driver_expert',
    skillKey: 'driverExpertSkill',
    supportsDeepCot: true,
    deepCotSystemPrompt: DRIVER_EXPERT_COT_SYSTEM_PROMPT,
    contextFlags: { latestReport: true, pendingClarification: true },
  },
  {
    domain: 'driver',
    taskType: 'report',
    workerTool: 'generate_driver_report',
    skillKey: 'driverSkill',
    contextFlags: { profile: true, pendingClarification: true },
  },
  {
    domain: 'vehicle',
    taskType: 'consult',
    workerTool: 'consult_vehicle_expert',
    skillKey: 'vehicleExpertSkill',
    supportsDeepCot: true,
    deepCotSystemPrompt: VEHICLE_EXPERT_COT_SYSTEM_PROMPT,
    contextFlags: { latestReport: true, pendingClarification: true },
  },
  {
    domain: 'vehicle',
    taskType: 'report',
    workerTool: 'generate_vehicle_report',
    skillKey: 'vehicleSkill',
    contextFlags: { profile: true, pendingClarification: true },
  },
  {
    domain: 'unit',
    taskType: 'consult',
    workerTool: 'consult_unit_expert',
    skillKey: 'unitExpertSkill',
    supportsDeepCot: true,
    deepCotSystemPrompt: UNIT_EXPERT_COT_SYSTEM_PROMPT,
    contextFlags: { latestReport: true, pendingClarification: true },
  },
  {
    domain: 'unit',
    taskType: 'report',
    workerTool: 'generate_unit_report',
    skillKey: 'unitSkill',
    contextFlags: { profile: true, pendingClarification: true },
  },
  {
    domain: 'route',
    taskType: 'consult',
    workerTool: 'consult_route_expert',
    skillKey: 'routeExpertSkill',
    supportsDeepCot: true,
    deepCotSystemPrompt: ROUTE_EXPERT_COT_SYSTEM_PROMPT,
    contextFlags: { latestReport: true, pendingClarification: true },
  },
  {
    domain: 'route',
    taskType: 'report',
    workerTool: 'generate_route_report',
    skillKey: 'routeSkill',
    contextFlags: { profile: true, pendingClarification: true },
  },
  {
    domain: 'station',
    taskType: 'consult',
    workerTool: 'consult_station_expert',
    skillKey: 'stationExpertSkill',
    supportsDeepCot: true,
    deepCotSystemPrompt:
      '推理模式：回答站场画像、风险分析或站场管理问题前，先在内部充分分析站场基础画像、综合风险、交通安全、三防安全、消防安全、管理闭环和同口径对比之间的一致性，然后只输出最终结论、关键依据、风险来源、管理建议和数据缺口。不要逐字暴露隐藏推理过程。',
    contextFlags: { latestReport: true, pendingClarification: true },
  },
  {
    domain: 'station',
    taskType: 'report',
    workerTool: 'generate_station_report',
    skillKey: 'stationSkill',
    contextFlags: { profile: true, pendingClarification: true },
  },
  {
    domain: 'incident',
    taskType: 'consult',
    workerTool: 'consult_incident_expert',
    skillKey: 'incidentExpertSkill',
    supportsDeepCot: true,
    deepCotSystemPrompt: INCIDENT_EXPERT_COT_SYSTEM_PROMPT,
    contextFlags: { latestReport: true, pendingClarification: true },
  },
  {
    domain: 'incident',
    taskType: 'report',
    workerTool: 'generate_accident_investigation_report',
    skillKey: 'accidentInvestigationSkill',
    contextFlags: { profile: true, pendingClarification: true },
  },
];

export function getExpertRegistryItem(
  domain: ExpertDomain,
  taskType: ExpertTaskType
): ExpertRegistryItem | null {
  return EXPERT_REGISTRY.find((item) => item.domain === domain && item.taskType === taskType) ?? null;
}

export function getExpertRegistryItemByWorkerTool(workerTool: string): ExpertRegistryItem | null {
  return EXPERT_REGISTRY.find((item) => item.workerTool === workerTool) ?? null;
}
