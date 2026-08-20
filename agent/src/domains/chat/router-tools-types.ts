export type RouterDispatchToolName =
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
  | 'request_further_info';

export type RouterToolName = RouterDispatchToolName | 'match_rules';

export interface RouterToolSchema {
  name: RouterToolName;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}
