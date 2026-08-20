type WorkerToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_unit_report'
  | 'generate_route_report'
  | 'generate_station_report'
  | 'generate_accident_investigation_report'
  | 'consult_omni'
  | 'consult_driver_expert'
  | 'consult_vehicle_expert'
  | 'consult_unit_expert'
  | 'consult_route_expert'
  | 'consult_station_expert'
  | 'consult_incident_expert'
  | 'rule_reply'
  | 'rule_asker'
  | 'rule_builder';

const TOOL_DESCRIPTIONS: Partial<Record<WorkerToolName, string>> = {
  generate_driver_report: '生成驾驶员画像报告',
  generate_vehicle_report: '生成车辆画像报告',
  generate_unit_report: '生成单位画像报告',
  generate_route_report: '生成线路画像报告',
  generate_accident_investigation_report: '生成事故调查与整改报告',
  consult_omni: '综合分析与问答',
  consult_driver_expert: '驾驶员专家分析与问答',
  consult_vehicle_expert: '车辆专家分析与问答',
  consult_unit_expert: '单位专家分析与问答',
  consult_route_expert: '线路专家分析与问答',
  consult_incident_expert: '事故专家分析与问答',
  rule_reply: '规则命中回复',
  rule_asker: '规则配置追问',
  rule_builder: '规则草稿结构化构建',
};

export function formatAgentError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('缺少 OPENAI_API_KEY') || message.includes('缂哄皯 OPENAI_API_KEY')) {
    return '模型服务未配置，请在 Worker 环境变量中设置 OPENAI_API_KEY。';
  }
  if (message.includes('模型服务错误') || message.includes('妯″瀷鏈嶅姟閿欒')) {
    return `模型服务调用失败：${message}`;
  }
  return `助手调用失败：${message}`;
}

export function getToolDescription(tool: WorkerToolName): string {
  return TOOL_DESCRIPTIONS[tool] || '工具调用';
}
