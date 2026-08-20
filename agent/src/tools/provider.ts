import { isKbToolEnabled } from '../infra/kb-query-tool';
import { executeProfileQuotaLookup } from '../shared/profile-quota-lookup';

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
  error_code?: number | string;
}

export type ToolProviderMode = 'local' | 'mcp' | 'hybrid' | 'scoped';

export interface ToolProviderDebugInfo {
  provider_mode: ToolProviderMode;
  base_provider_mode?: ToolProviderMode;
  mcp_configured: boolean;
  mcp_visible?: boolean | null;
  mcp_list_failed?: boolean;
  mcp_list_error?: string | null;
  mcp_tool_names?: string[];
  allow_list?: string[];
  kb_tool_enabled?: boolean;
  kb_api_configured?: boolean;
  kb_default_id?: string;
}

export interface ToolProvider {
  listTools(): Promise<ToolDefinition[]>;
  callTool(name: string, args: Record<string, unknown>): Promise<ToolResult>;
  getDebugInfo?(): Promise<ToolProviderDebugInfo> | ToolProviderDebugInfo;
}

export interface LocalToolProviderEnv {
  DB: unknown;
  KB_API_BASE_URL?: string;
  KB_DEFAULT_ID?: string;
  KB_TOOL_ENABLED?: string;
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
  MCP_REQUEST_TIMEOUT_MS?: string;
}

export interface McpToolClient {
  listTools(config: McpToolConfig): Promise<ToolDefinition[]>;
  callTool(config: McpToolConfig, name: string, args: Record<string, unknown>): Promise<ToolResult>;
}

export interface McpToolConfig {
  serverUrl?: string;
  clientId?: string;
  clientSecret?: string;
  accessToken?: string;
  requestTimeoutMs?: number | string;
}

export interface LocalToolExecutors {
  executeGetRule(db: unknown, args: Record<string, unknown>): Promise<ToolResult>;
  executeGetRuleDraft(db: unknown, args: Record<string, unknown>): Promise<ToolResult>;
  executeUpdateRuleDraft(db: unknown, args: Record<string, unknown>): Promise<ToolResult>;
  executeSubmitRuleTurn(db: unknown, args: Record<string, unknown>): Promise<ToolResult>;
  executeQueryKb(env: LocalToolProviderEnv, args: Record<string, unknown>): Promise<ToolResult>;
  buildPendingFurtherInfoToolPayload(args: Record<string, unknown>): unknown | null;
}

export interface CreateToolProviderOptions {
  env: LocalToolProviderEnv;
  executors: LocalToolExecutors;
  mcpClient: McpToolClient;
}

class LocalToolProvider implements ToolProvider {
  constructor(private env: LocalToolProviderEnv, private executors: LocalToolExecutors) {}

  async listTools(): Promise<ToolDefinition[]> {
    const tools: ToolDefinition[] = [
      {
        name: 'get_rule',
        description: 'Get rule details by rule_id.',
        parameters: {
          type: 'object',
          properties: {
            rule_id: { type: 'string', description: 'Rule ID.' },
          },
          required: ['rule_id'],
        },
      },
      {
        name: 'get_rule_draft',
        description: 'Get the current rule draft state by session_id.',
        parameters: {
          type: 'object',
          properties: {
            session_id: { type: 'string', description: 'Session ID.' },
            sessionId: { type: 'string', description: 'Session ID alias.' },
          },
          required: ['session_id'],
        },
      },
      {
        name: 'update_rule_draft',
        description: 'Update the rule draft state for the current rule configuration conversation.',
        parameters: {
          type: 'object',
          properties: {
            session_id: { type: 'string', description: 'Session ID.' },
            sessionId: { type: 'string', description: 'Session ID alias.' },
            status: {
              type: 'string',
              enum: [
                'collecting',
                'awaiting_confirm',
                'compiling',
                'rework',
                'blocked_conflict',
                'saved',
                'cancelled',
                'ready_for_confirm',
                'blocked',
              ],
              description: 'Draft status.',
            },
            mode: { type: 'string', enum: ['create', 'edit'], description: 'Draft mode.' },
            rule_id: { type: 'string', description: 'Rule ID for edit mode.' },
            ruleId: { type: 'string', description: 'Rule ID alias.' },
            draft: { type: 'object', description: 'Draft payload.' },
            noop: { type: 'boolean', description: 'Refresh status/timestamp without draft changes.' },
          },
          required: ['session_id'],
        },
      },
      {
        name: 'submit_rule_turn',
        description: 'Submit a structured rule configuration proposal for this turn without writing a final rule.',
        parameters: {
          type: 'object',
          properties: {
            session_id: { type: 'string', description: 'Session ID.' },
            patch: { type: 'object', description: 'Draft patch extracted from this turn.' },
            operations: {
              type: 'array',
              description: 'Structured edit operations for rule draft fields.',
              items: {
                type: 'object',
                properties: {
                  field: { type: 'string', description: 'Target field.' },
                  op: {
                    type: 'string',
                    enum: ['set', 'append', 'remove', 'clear'],
                    description: 'Field operation.',
                  },
                  value: { description: 'Operation value.' },
                },
                required: ['field', 'op'],
              },
            },
            field_meta: { type: 'object', description: 'Field metadata by field name.' },
            intent: {
              type: 'string',
              enum: ['provide_info', 'confirm', 'revise', 'cancel', 'unknown'],
              description: 'User intent in this turn.',
            },
            next_question: { type: 'string', description: 'Suggested next single clarification question.' },
            missing_fields_guess: {
              type: 'array',
              items: { type: 'string' },
              description: 'Fields estimated to still be missing.',
            },
          },
          required: ['session_id', 'intent'],
        },
      },
      {
        name: 'rule_exit',
        description: 'Exit current rule handling and hand off the message to Router.',
        parameters: {
          type: 'object',
          properties: {
            reason: { type: 'string', description: 'Exit reason.' },
            confidence: { type: 'number', description: 'Confidence from 0 to 1.' },
          },
        },
      },
      {
        name: 'request_further_info',
        description:
          'Persist resumable pending context for the next user turn when more information is needed. Send the user-facing clarification in the assistant message content, not in tool args.',
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
              description: 'Worker tool to resume after the user provides more information.',
            },
            resume_mode: {
              type: 'string',
              enum: ['fill_args', 'append_user_reply'],
              description: 'How to merge the next user reply when resuming.',
            },
            missing_fields: {
              type: 'array',
              items: { type: 'string' },
              description: 'Missing args or logical slots that the next user turn should provide.',
            },
            known_args: {
              type: 'object',
              description: 'Known worker args already collected for the resume tool.',
            },
            options: {
              type: 'array',
              description: 'Optional candidate choices for the user to select from.',
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
            direct_resume: {
              type: 'boolean',
              description: 'Whether the next short user reply can be auto-resumed before router.',
            },
          },
          required: ['resume_tool'],
        },
      },
      {
        name: 'get_profile_quota_by_name',
        description:
          [
            'Query a profile entity by business name, then return all quotaScoreSubList items whose quotaName matches the requested Chinese indicator name.',
            'Use this when the user asks for a concrete profile risk indicator by display name, such as 急加速, 急减速, 急刹车, 空档滑行, 斑马线超速, or similar.',
            'This tool resolves quotaName to every matching full quotaId/path and returns all matches; do not put a short Chinese quotaName directly into a quotaId parameter when this tool is available.',
            'Supported entityType values: driver, vehicle, route, unit, station, accident.',
          ].join(' '),
        parameters: {
          type: 'object',
          properties: {
            entityType: {
              type: 'string',
              enum: ['driver', 'vehicle', 'route', 'unit', 'station', 'accident'],
              description: 'Profile subject type.',
            },
            entityName: {
              type: 'string',
              description:
                'Business name or identifier for the entity. For vehicle this may be the number plate; for accident this is the organization name used by the accident profile endpoint.',
            },
            driverName: { type: 'string', description: 'Driver name alias for entityName.' },
            numberPlate: { type: 'string', description: 'Vehicle number plate alias for entityName.' },
            routeName: { type: 'string', description: 'Route name alias for entityName.' },
            organName: { type: 'string', description: 'Organization name alias for entityName.' },
            busStationName: { type: 'string', description: 'Bus station name alias for entityName.' },
            quotaName: {
              type: 'string',
              description:
                'Display indicator name to match against quotaScoreSubList[].quotaName, for example 急加速.',
            },
            ppartition: {
              type: 'string',
              description: 'Profile date partition in yyyyMMdd format.',
            },
            matchMode: {
              type: 'string',
              enum: ['exact', 'contains'],
              description:
                'exact matches quotaName exactly; contains returns quota names containing the input. Default exact.',
            },
          },
          required: ['entityType', 'quotaName'],
        },
      },
    ];

    if (isKbToolEnabled(this.env)) {
      tools.push({
        name: 'query_kb',
        description:
          [
            'Query the institutional knowledge base for policies, regulations, notices, procedures, responsibilities, applicability, complaint handling, safety/fire-safety, risk, hidden-danger, and other rule evidence.',
            'Use retrieve when the user asks to find a regulation, article, clause, file number, document title, policy basis, obligation, prohibition, process, time limit, classification, or responsibility.',
            'Use retrieve with the exact document title or file number when the user names a document; title/file-number queries use a fast document-title path.',
            'After retrieve, use get_document with the returned doc_id when the user asks for the full document, surrounding clauses, or next/previous context.',
            'Use list_documents only when the user asks what knowledge-base documents are available.',
            'Do not call this tool for ordinary conversation, calculation, report prose editing, dashboard/data questions, or entity profile lookups unless the user explicitly asks for policy/regulation evidence.',
            'When answering from retrieved items, cite the document title and field_path, and distinguish direct evidence from inference.',
          ].join(' '),
        parameters: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['retrieve', 'get_document', 'list_documents'],
              description:
                'retrieve = search clauses by natural-language query, document title, or file number; get_document = open one returned document by doc_id; list_documents = browse available documents.',
            },
            kb_id: {
              type: 'string',
              description: 'Knowledge base ID. Defaults to KB_DEFAULT_ID.',
            },
            query: {
              type: 'string',
              description:
                'Query text for retrieve. Prefer exact user wording for clause searches; use exact file number/title for document lookup; include key terms like article, obligation, responsibility, process, or applicability when present.',
            },
            doc_id: {
              type: 'string',
              description: 'Document ID returned by retrieve/list_documents for get_document.',
            },
            top_k: {
              type: 'number',
              description: 'Number of passages to return for retrieve. Use 3-5 for normal answers, up to 8 for debugging or broad exploration.',
            },
            include_clauses: {
              type: 'boolean',
              description: 'Whether get_document should include clause content. Set true when the user needs surrounding clauses or full document context.',
            },
            limit: {
              type: 'number',
              description: 'Page size for list_documents.',
            },
            offset: {
              type: 'number',
              description: 'Page offset for list_documents.',
            },
          },
          required: ['action'],
        },
      });
    }

    return tools;
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<ToolResult> {
    if (name === 'get_rule') {
      return this.executors.executeGetRule(this.env.DB, args);
    }
    if (name === 'get_rule_draft') {
      return this.executors.executeGetRuleDraft(this.env.DB, args);
    }
    if (name === 'update_rule_draft') {
      return this.executors.executeUpdateRuleDraft(this.env.DB, args);
    }
    if (name === 'submit_rule_turn') {
      return this.executors.executeSubmitRuleTurn(this.env.DB, args);
    }
    if (name === 'rule_exit') {
      const reason = typeof args?.reason === 'string' ? args.reason : undefined;
      const confidence =
        typeof args?.confidence === 'number' && Number.isFinite(args.confidence) ? args.confidence : undefined;
      return { success: true, data: { exit: true, reason, confidence } };
    }
    if (name === 'request_further_info') {
      const payload = this.executors.buildPendingFurtherInfoToolPayload(args);
      if (!payload) {
        return { success: false, error: 'resume_tool is required' };
      }
      return { success: true, data: payload };
    }
    if (name === 'query_kb') {
      return this.executors.executeQueryKb(this.env, args);
    }
    if (name === 'get_profile_quota_by_name') {
      return executeProfileQuotaLookup(this.env, args);
    }
    return { success: false, error: `Unknown tool: ${name}` };
  }

  getDebugInfo() {
    return {
      provider_mode: 'local' as const,
      mcp_configured: false,
      mcp_visible: false,
      mcp_tool_names: [],
      kb_tool_enabled: isKbToolEnabled(this.env),
      kb_api_configured: Boolean(String(this.env.KB_API_BASE_URL ?? '').replace(/\/+$/, '')),
      kb_default_id: String(this.env.KB_DEFAULT_ID || 'regulations'),
    };
  }
}

export class ScopedToolProvider implements ToolProvider {
  constructor(
    private base: ToolProvider,
    private overrides: Record<string, (args: Record<string, unknown>) => Promise<ToolResult> | ToolResult> = {},
    private allowList?: Set<string>,
    private overrideDefinitions: Record<string, ToolDefinition> = {}
  ) {}

  async listTools(): Promise<ToolDefinition[]> {
    const tools = await this.base.listTools();
    const merged = new Map<string, ToolDefinition>();
    for (const tool of tools) {
      merged.set(tool.name, tool);
    }
    for (const [name, definition] of Object.entries(this.overrideDefinitions)) {
      merged.set(name, definition);
    }
    const mergedTools = Array.from(merged.values());
    if (!this.allowList) return mergedTools;
    return mergedTools.filter((tool) => this.allowList!.has(tool.name) || tool.name === 'request_further_info');
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<ToolResult> {
    if (this.allowList && !this.allowList.has(name) && name !== 'request_further_info') {
      return { success: false, error: `Tool not allowed in current scope: ${name}` };
    }
    const override = this.overrides[name];
    if (override) {
      return await override(args);
    }
    return this.base.callTool(name, args);
  }

  async getDebugInfo() {
    const baseInfo = await this.base.getDebugInfo?.();
    const allowList = this.allowList ? Array.from(this.allowList).sort() : undefined;
    const scopedMcpToolNames = baseInfo?.mcp_tool_names
      ? (this.allowList
          ? baseInfo.mcp_tool_names.filter((name) => this.allowList!.has(name))
          : [...baseInfo.mcp_tool_names]
        ).sort()
      : undefined;
    return {
      provider_mode: 'scoped' as const,
      ...(baseInfo?.provider_mode ? { base_provider_mode: baseInfo.provider_mode } : {}),
      mcp_configured: baseInfo?.mcp_configured ?? false,
      ...(baseInfo?.mcp_visible !== undefined ? { mcp_visible: baseInfo.mcp_visible } : {}),
      ...(baseInfo?.mcp_list_failed !== undefined ? { mcp_list_failed: baseInfo.mcp_list_failed } : {}),
      ...(baseInfo?.mcp_list_error !== undefined ? { mcp_list_error: baseInfo.mcp_list_error } : {}),
      ...(scopedMcpToolNames ? { mcp_tool_names: scopedMcpToolNames } : {}),
      ...(allowList ? { allow_list: allowList } : {}),
    };
  }
}

class MCPToolProvider implements ToolProvider {
  private lastToolNames: string[] = [];
  private lastListFailed = false;
  private lastListError: string | null = null;
  private hasListedTools = false;

  constructor(
    private mcpClient: McpToolClient,
    private serverUrl?: string,
    private clientId?: string,
    private clientSecret?: string,
    private accessToken?: string,
    private requestTimeoutMs?: string
  ) {}

  async listTools(): Promise<ToolDefinition[]> {
    this.hasListedTools = true;
    try {
      const tools = await this.mcpClient.listTools({
        serverUrl: this.serverUrl,
        clientId: this.clientId,
        clientSecret: this.clientSecret,
        accessToken: this.accessToken,
        requestTimeoutMs: this.requestTimeoutMs,
      });
      this.lastToolNames = tools.map((tool) => tool.name).sort();
      this.lastListFailed = false;
      this.lastListError = null;
      return tools;
    } catch (error) {
      this.lastToolNames = [];
      this.lastListFailed = true;
      this.lastListError = error instanceof Error ? error.message : String(error);
      throw error;
    }
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<ToolResult> {
    return this.mcpClient.callTool(
      {
        serverUrl: this.serverUrl,
        clientId: this.clientId,
        clientSecret: this.clientSecret,
        accessToken: this.accessToken,
        requestTimeoutMs: this.requestTimeoutMs,
      },
      name,
      args
    );
  }

  getDebugInfo() {
    return {
      provider_mode: 'mcp' as const,
      mcp_configured: Boolean(this.serverUrl),
      ...(this.hasListedTools ? { mcp_visible: !this.lastListFailed } : { mcp_visible: null }),
      mcp_list_failed: this.lastListFailed,
      ...(this.lastListError !== null ? { mcp_list_error: this.lastListError } : {}),
      mcp_tool_names: [...this.lastToolNames],
    };
  }
}

class HybridToolProvider implements ToolProvider {
  private primaryToolNames: Set<string> | null | undefined;
  private lastPrimaryToolNames: string[] = [];
  private lastPrimaryListFailed = false;
  private lastPrimaryListError: string | null = null;
  private hasListedPrimaryTools = false;

  constructor(private primary: ToolProvider, private fallback: ToolProvider) {}

  private async listPrimaryToolsSafe(): Promise<ToolDefinition[]> {
    this.hasListedPrimaryTools = true;
    try {
      const tools = await this.primary.listTools();
      this.primaryToolNames = new Set(tools.map((tool) => tool.name));
      this.lastPrimaryToolNames = tools.map((tool) => tool.name).sort();
      this.lastPrimaryListFailed = false;
      this.lastPrimaryListError = null;
      return tools;
    } catch (error) {
      this.primaryToolNames = null;
      this.lastPrimaryToolNames = [];
      this.lastPrimaryListFailed = true;
      this.lastPrimaryListError = error instanceof Error ? error.message : String(error);
      console.warn('Primary tool provider listTools failed, using fallback tools only.', {
        error: error instanceof Error ? error.message : String(error),
      });
      return [];
    }
  }

  private async getPrimaryToolNames(): Promise<Set<string> | null> {
    if (this.primaryToolNames !== undefined) {
      return this.primaryToolNames;
    }
    await this.listPrimaryToolsSafe();
    return this.primaryToolNames ?? null;
  }

  async listTools(): Promise<ToolDefinition[]> {
    const [primaryTools, fallbackTools] = await Promise.all([
      this.listPrimaryToolsSafe(),
      this.fallback.listTools(),
    ]);
    const merged = new Map<string, ToolDefinition>();
    for (const tool of fallbackTools) {
      merged.set(tool.name, tool);
    }
    for (const tool of primaryTools) {
      merged.set(tool.name, tool);
    }
    return Array.from(merged.values());
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<ToolResult> {
    const primaryToolNames = await this.getPrimaryToolNames();
    const shouldTryPrimary = !primaryToolNames || primaryToolNames.has(name);
    if (shouldTryPrimary) {
      try {
        const result = await this.primary.callTool(name, args);
        if (result.success || !isToolNotFoundLikeError(result.error)) {
          return result;
        }
        console.warn('Primary tool provider does not expose requested tool, falling back.', {
          tool: name,
          error: result.error,
        });
      } catch (error) {
        console.warn('Primary tool provider call failed, falling back.', {
          tool: name,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
    return this.fallback.callTool(name, args);
  }

  async getDebugInfo() {
    const fallbackInfo = await this.fallback.getDebugInfo?.();
    return {
      provider_mode: 'hybrid' as const,
      mcp_configured: true,
      ...(this.hasListedPrimaryTools
        ? { mcp_visible: !this.lastPrimaryListFailed }
        : { mcp_visible: null }),
      mcp_list_failed: this.lastPrimaryListFailed,
      ...(this.lastPrimaryListError !== null ? { mcp_list_error: this.lastPrimaryListError } : {}),
      mcp_tool_names: [...this.lastPrimaryToolNames],
      ...(fallbackInfo?.kb_tool_enabled !== undefined ? { kb_tool_enabled: fallbackInfo.kb_tool_enabled } : {}),
      ...(fallbackInfo?.kb_api_configured !== undefined ? { kb_api_configured: fallbackInfo.kb_api_configured } : {}),
      ...(fallbackInfo?.kb_default_id ? { kb_default_id: fallbackInfo.kb_default_id } : {}),
    };
  }
}

function isToolNotFoundLikeError(message: string | undefined): boolean {
  const normalized = String(message ?? '').trim().toLowerCase();
  if (!normalized) return false;
  return (
    normalized.includes('not found') ||
    normalized.includes('unknown tool') ||
    normalized.includes('unsupported tool') ||
    normalized.includes('tool not found') ||
    normalized.includes('no such tool') ||
    normalized.includes('method not found')
  );
}

export function createToolProvider(options: CreateToolProviderOptions): ToolProvider {
  const { env, executors, mcpClient } = options;
  const fallback = new LocalToolProvider(env, executors);

  if (env.MCP_SERVER_URL) {
    return new HybridToolProvider(
      new MCPToolProvider(
        mcpClient,
        env.MCP_SERVER_URL,
        env.CF_ACCESS_CLIENT_ID,
        env.CF_ACCESS_CLIENT_SECRET,
        env.MCP_ACCESS_TOKEN,
        env.MCP_REQUEST_TIMEOUT_MS
      ),
      fallback
    );
  }
  return fallback;
}
