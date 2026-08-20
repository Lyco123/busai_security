import type { RouterDispatchToolName, RouterToolSchema } from './router-tools-types';

export type {
  RouterDispatchToolName,
  RouterToolName,
  RouterToolSchema,
} from './router-tools-types';

export type OpenAIRouterTool = { type: 'function'; function: RouterToolSchema };

// Router tool descriptions are intentionally compact. If routing recall changes,
// check agent/docs/router-optimization-20260518.md before expanding them again.
const REPORT_BOUNDARY =
  '仅用于用户明确索取唯一对象的正式报告、画像报告或风险总结；查询、解释、对比、建议、明细、要点、确认是否有数据，或明确不要正式报告时不得使用。';

const CONSULT_MODE =
  'cot_mode: direct=简单事实、基础信息、单点解释；deep=复杂归因、趋势/对比、综合分析、管理建议或报告追问。';

const PARTITION_DESCRIPTION =
  '可选报告日期分区。优先传 yyyyMMdd；用户未指定时不要自行填写，由系统查询最新画像日期。';

const TOOLS: OpenAIRouterTool[] = [
  {
    type: 'function',
    function: {
      name: 'match_rules',
      description: '补查规则匹配结果。通常规则结果已由系统注入，只有缺失或系统明确要求时使用。',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '用户查询文本' },
          top_k: { type: 'number', description: '返回数量，默认 5' },
          min_score: { type: 'number', description: '最小相似度，默认 0.3' },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'generate_driver_report',
      description: `${REPORT_BOUNDARY} 对象类型：驾驶员。咨询和报告追问改用 consult_driver_expert 或 consult_omni。`,
      parameters: {
        type: 'object',
        properties: {
          driver_name: { type: 'string', description: '驾驶员姓名' },
          ppartition: { type: 'string', description: PARTITION_DESCRIPTION },
        },
        required: ['driver_name'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'generate_vehicle_report',
      description: `${REPORT_BOUNDARY} 对象类型：车辆。咨询和报告追问改用 consult_vehicle_expert 或 consult_omni。`,
      parameters: {
        type: 'object',
        properties: {
          numberPlate: {
            type: 'string',
            description:
              '车辆车牌号。当前只支持粤A/粤E车辆；缺省“粤”但保留 A/E 时可传入。只有尾号时先澄清。',
          },
          ppartition: { type: 'string', description: PARTITION_DESCRIPTION },
        },
        required: ['numberPlate'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'generate_unit_report',
      description: `${REPORT_BOUNDARY} 对象类型：单位。咨询和报告追问改用 consult_unit_expert 或 consult_omni。`,
      parameters: {
        type: 'object',
        properties: {
          organ_name: { type: 'string', description: '单位名称' },
          ppartition: { type: 'string', description: PARTITION_DESCRIPTION },
        },
        required: ['organ_name'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'generate_route_report',
      description: `${REPORT_BOUNDARY} 对象类型：线路。咨询和报告追问改用 consult_route_expert。`,
      parameters: {
        type: 'object',
        properties: {
          route_name: { type: 'string', description: '线路名称或线路编号' },
          ppartition: { type: 'string', description: PARTITION_DESCRIPTION },
        },
        required: ['route_name'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'generate_station_report',
      description: `${REPORT_BOUNDARY} 对象类型：站场/总站/车站。咨询和报告追问改用 consult_station_expert 或 consult_omni。`,
      parameters: {
        type: 'object',
        properties: {
          station_name: { type: 'string', description: '站场、总站或车站名称' },
          ppartition: { type: 'string', description: PARTITION_DESCRIPTION },
        },
        required: ['station_name'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'generate_accident_investigation_report',
      description: `${REPORT_BOUNDARY} 对象类型：事故。只有完整事故调查报告、整改报告或复盘报告成品请求才使用；事故信息查询或原因建议改用 consult_incident_expert 或 consult_omni。需提供肇事驾驶员姓名和事故发生日期。`,
      parameters: {
        type: 'object',
        properties: {
          driver_name: { type: 'string', description: '肇事驾驶员姓名' },
          accident_date: {
            type: 'string',
            description: '事故发生时间，格式 yyyyMMddHHmmss，例如 20251231050505',
          },
        },
        required: ['driver_name', 'accident_date'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'consult_omni',
      description:
        '通用咨询、跨主题总结、制度流程说明、车队/单位/线路/车辆/驾驶员/站场的基础数据、基础信息、运营基础数据、基础运营数据、档案、台账、列表、数量统计，以及没有专门专家承接的非报告型问题。若问题主体明确是风险、画像、评分、原因、整改、管理效果或报告追问，优先对应 consult_*_expert。',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '咨询问题' },
          context: { type: 'string', description: '可选补充上下文' },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'consult_driver_expert',
      description: `驾驶员专家咨询：明确驾驶员的风险、画像、安全状态、指标成因、趋势、对比、管理闭环、整改建议或报告追问。报告成品改用 generate_driver_report。${CONSULT_MODE}`,
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '驾驶员相关咨询问题' },
          context: { type: 'string', description: '可选补充上下文' },
          cot_mode: { type: 'string', enum: ['direct', 'deep'], description: CONSULT_MODE },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'consult_vehicle_expert',
      description: `车辆专家咨询：明确车辆的风险、画像、健康/安全状态、异常原因、能耗、维保整改、运营判断、对比或报告追问。报告成品改用 generate_vehicle_report；车队级元数据/列表/统计用 consult_omni。${CONSULT_MODE}`,
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '车辆相关咨询问题' },
          context: { type: 'string', description: '可选补充上下文' },
          cot_mode: { type: 'string', enum: ['direct', 'deep'], description: CONSULT_MODE },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'consult_unit_expert',
      description: `单位专家咨询：明确单位的风险、画像、安全状态、管理效果、趋势、下级风险来源、整改建议或报告追问。报告成品改用 generate_unit_report；单位基础数据、基础信息、运营基础数据、基础运营数据、档案、台账、车辆数、驾驶员人数、线路数、站场数等列表/数量统计，应使用 consult_omni。${CONSULT_MODE}`,
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '单位相关咨询问题' },
          context: { type: 'string', description: '可选补充上下文' },
          cot_mode: { type: 'string', enum: ['direct', 'deep'], description: CONSULT_MODE },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'consult_route_expert',
      description: `线路专家咨询：明确线路的风险、画像、风险构成、黑点路段、运行特征、波动、管理动作、对比或报告追问。报告成品改用 generate_route_report；纯站点/班次/列表统计可用 consult_omni。${CONSULT_MODE}`,
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '线路相关咨询问题' },
          context: { type: 'string', description: '可选补充上下文' },
          cot_mode: { type: 'string', enum: ['direct', 'deep'], description: CONSULT_MODE },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'consult_station_expert',
      description: `站场专家咨询：明确站场的风险、画像、安全状态、评分/分数、交通/三防/消防风险、整改建议、管理闭环或报告追问。报告成品改用 generate_station_report；纯列表/统计可用 consult_omni。${CONSULT_MODE}`,
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '站场相关咨询问题' },
          context: { type: 'string', description: '可选补充上下文' },
          cot_mode: { type: 'string', enum: ['direct', 'deep'], description: CONSULT_MODE },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'consult_incident_expert',
      description: `事故专家咨询：单起事故的经过、基础信息、证据、原因、责任性质、整改措施、处理进度或报告追问。完整事故调查/整改/复盘报告成品改用 generate_accident_investigation_report；事故列表/数量/台账统计可用 consult_omni。${CONSULT_MODE}`,
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '事故相关咨询问题' },
          context: { type: 'string', description: '可选补充上下文' },
          cot_mode: { type: 'string', enum: ['direct', 'deep'], description: CONSULT_MODE },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'rule_reply',
      description:
        '执行当前轮已明确选定的已保存规则。必须提供本轮规则匹配结果中的 rule_id；没有规则命中或拿不准具体规则时不得调用。',
      parameters: {
        type: 'object',
        properties: {
          user_query: { type: 'string', description: '用户原始问题' },
          rule_id: { type: 'string', description: '当前轮选定的规则 ID' },
          hit_rules: {
            type: 'array',
            items: { type: 'object' },
            description: '可选，仅作为参考的本轮命中规则列表；不能替代 rule_id。',
          },
        },
        required: ['user_query', 'rule_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'request_further_info',
      description:
        '当前轮缺少关键对象、日期、范围或意图时使用。用户可见澄清语放在 assistant content，工具参数只保存可恢复的待补充状态。',
      parameters: {
        type: 'object',
        properties: {
          resume_tool: {
            type: 'string',
            enum: [
              'generate_driver_report',
              'generate_vehicle_report',
              'generate_unit_report',
              'generate_route_report',
              'generate_station_report',
              'generate_accident_investigation_report',
              'consult_omni',
              'consult_driver_expert',
              'consult_vehicle_expert',
              'consult_unit_expert',
              'consult_route_expert',
              'consult_station_expert',
              'consult_incident_expert',
              'rule_reply',
              'rule_asker',
              'rule_builder',
            ],
            description: '用户补充信息后要恢复的工具',
          },
          resume_mode: { type: 'string', enum: ['fill_args', 'append_user_reply'] },
          missing_fields: {
            type: 'array',
            items: { type: 'string' },
            description: '下一轮需要用户补充的槽位或逻辑字段',
          },
          known_args: { type: 'object', description: '已经确认的恢复参数' },
          options: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                label: { type: 'string' },
                value: { type: 'string' },
                aliases: { type: 'array', items: { type: 'string' } },
              },
              required: ['label', 'value'],
            },
          },
          direct_resume: { type: 'boolean' },
        },
        required: ['resume_tool'],
      },
    },
  },
];

export function buildRouterTools(
  toolAllowList?: readonly RouterDispatchToolName[]
): OpenAIRouterTool[] {
  // Contract: undefined means "all router tools"; [] means "no tools".
  // The no-tools case is used by router-owned clarification rewriting.
  if (toolAllowList !== undefined) {
    const allowSet = new Set(toolAllowList);
    return TOOLS.filter((tool) => allowSet.has(tool.function.name as RouterDispatchToolName));
  }

  return [...TOOLS];
}
