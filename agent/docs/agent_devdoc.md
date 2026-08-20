---
todo_reminder:
  - feature: "State Machine Slot Management (状态机槽位管理)"
    scope: "System-wide (Global)"
    status: "Pending Design"
    description: "引入显式的状态机和 Slot Filling 机制来管理多轮对话和信息收集。这不仅适用于规则系统，对整个系统的稳定性都非常重要。需要进一步设计通用的 Context 结构和状态流转逻辑。"
---
# 系统设计文档：智能公交安全助理

## 0. 技术栈说明

### 当前实现（Dev/Demo 版本）
- **后端**：TypeScript + Cloudflare Workers
- **前端**：TypeScript + React/Vite（演示用）
- **状态**：用于开发和演示，功能完整但部分高级特性待实现

### 生产环境计划
- **后端**：Python（待实现）
- **前端**：外包开发
- **状态**：本文档主要描述生产环境的设计方案

**注意**：本文档中的代码示例和目录结构主要针对**生产环境（Python）**，当前 TypeScript 实现作为参考和过渡版本。

---

## 1. 核心摘要
本系统是一个基于 **智能体工作流** 架构的**智能公交安全助理**，旨在帮助用户分析和管理公交车队的"人、车、路"安全数据。

系统提供多种功能，包括但不限于：生成专业的安全评估报告、数据查询分析、安全建议咨询、公司规定咨询等。

系统突破了传统聊天机器人的限制，通过解耦 **决策（Router LLM）**、**数据检索（MCP Tools）**、**分析（Worker LLM）** 和 **文档生产（Code Runtime）**，实现高度模块化和专业化的智能助理服务。

---

## 2. 高层架构：三层"汉堡"模型 + 技能分流策略
系统由三个智能层级组成，中间由 **代码运行时** 作为"胶水"进行连接。系统采用**技能分流策略**，通过 Router 层面的决策实现物理隔离，确保输出格式的稳定性和一致性。


> 从系统视角看，这是一个 **低语义、高可靠性的调度层**。

| 层级 | 组件名称 | 核心职责 | 医院比喻 |
| :--- | :--- | :--- | :--- |
| **第 1 层** | **Router Agent (路由智能体)** | **规则优先** / 意图识别 / 分流决策 | **医院分诊台**：先看明确挂号规则，再根据分诊守则和科室说明决定送往“检验科”还是“专科门诊”。场景表只负责院外拦截。 |
| **第 2 层** | **MCP & Runtime (执行层)** | 数据抓取 / 上下文注入 / **技能模板加载** | 检验科 + 病历系统：按分诊结果调取化验、影像、既往病历，并加载对应诊疗流程规范（= runtime + context loader + MCP） |
| **第 3 层** | **Worker Agent (分析智能体)** | 数据分析 / 内容生成（**单一职责**） | **专科医生**：<br>1. **Report Worker (技师)**：出具结构化检验单 (JSON)；<br>2. **Omni Worker (医师)**：进行复杂诊断和咨询 (Markdown)。 |
| **第 4 层** | **Post-Process (后处理)** | 格式修复与双轨交付 | **质量保障**：格式修复（JSON_repair/Markdown修复）→ A轨→Artifact交付（文件存储+链接）；B轨→Interactive交付（流式推送+即时展示）。 |

### 2.1 技能分流策略 (Forking)

**核心思想**：不在同一个 Prompt 中混合两种输出模式指令，而是通过 **Router 层面的分流决策** 和 **技能模板的物理隔离**，确保每个 Worker 只专注一种输出格式。

系统根据 Router 识别的工具类型，采用两种完全隔离的输出路径：

| 场景 | Router 工具调用 | 技能模板路径 | Runtime 强制参数 | 输出格式 | 交付方式 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **路径 A** | `generate_report` | `skills/structured/` | `response_format: { type: "json_object" }` | **Strict JSON** | **Artifact 交付**：生成文件/包（PDF/ZIP/CSV等）→ 存储 → 返回链接/ID |
| **路径 B** | `consult_*` / `query_*` / `rule_reply` | `skills/conversational/` | `stream: True` | **Markdown** | **Interactive 交付**：流式/分段推送到前端（SSE/WS），支持即时展示与追问 |

**关键原则**：
* **物理隔离**：不同技能模板是不同 SIKILL，互不干扰
* **参数隔离**：最好通过 API 级别的参数强制输出格式（如 JSON mode）
* **单一职责**：每个技能模板只专注一件事，不包含 if-else 逻辑

---

## 3. 详细工作流程 (Detailed Workflow)

### 第一阶段：路由决策与分流 (The Routing & Gatekeeping)

Router 采用 **两级优先级决策**（命中即停）：

1.  **输入**：用户发送指令。
2.  **第一优先级 — 规则匹配（Rule Match）**：
    *   Runtime **总是**在 Router LLM 执行前运行 `match_rules`，并将结果以 `[RULE_MATCH_RESULTS]` 注入 Router 上下文（Router 本身不调用该工具）。
    *   `match_rules` 使用 Embedding 模型对用户查询进行向量化，与规则库进行相似度匹配。
    *   **匹配策略**：Anchor (match_text) + Examples (样例问题语料) 混合检索，Max Fusion 策略聚合得分。
    *   返回 topK 匹配结果（rule_id + score + metadata）。
    *   **决策规则**：若 top1 score ≥ 0.7 → 优先评估是否派单 `rule_reply`。多条高分且分差 < 0.05 时，Router 根据用户意图选择最匹配的一条。
3.  **业务门控 — 工作场景表（Work Scenario Table）**：
    *   Runtime 在 Router 前使用工作场景表做业务范围门控。
    *   **未命中/闲聊** $\rightarrow$ Runtime 直接拒绝，**流程结束**。
    *   **命中** $\rightarrow$ 继续进入 Router，由 Router 根据规则结果、技能说明和工具描述做分流。
4.  **分流派单**：
    *   **报表类工具** (`generate_*`) $\rightarrow$ 派单给 **Report Worker** (路径 A)
    *   **分析/咨询类工具** (`consult_*`) $\rightarrow$ 派单给 **Omni Worker** (路径 B)

### 第二阶段：执行与技能加载 (The "Glue" & Skill Loading)
1.  **代码运行时**：捕获 Router 的派单指令。
2.  **技能加载**：
    *   **路径 A**：加载 `skills/structured/` (Report Worker 技能)
    *   **路径 B**：加载 `skills/conversational/` (Omni Worker 技能)
3.  **工具提供者初始化**：
    *   创建 `ToolProvider` 实例（当前为 `LocalToolProvider`）
    *   动态获取可用工具列表（支持未来 MCP 动态发现）
4.  **数据查询**：Worker 通过 `query_data` 工具获取数据
    *   **当前实现**：`LocalToolProvider` 直接调用本地 `executeQueryData` 函数
    *   **未来计划**：通过 MCP 协议调用外部数据服务
5.  **数据注入**：查询结果注入到技能模板中

### 第三阶段：深度分析 - 单一职责执行

1.  **Worker LLM**：接收任务。**注意：Worker 不需要知道"工作场景表"的存在，它只负责执行被指派的任务。**
2.  **单一职责输出**：

    **路径 A：Report Worker (结构化处理机)**
    *   **职责**：只负责将数据转化为符合 Schema 的 JSON。
    *   **输出**：Strict JSON。
    *   **适用**：正式报告、存档记录。

    **路径 B：Omni Worker (全能分析师)**
    *   **职责**：处理复杂逻辑、多源数据分析、政策咨询。
    *   **输出**：Markdown 流式文本。
    *   **适用**：原因分析、趋势解读、法规问答。

### 第四阶段：后处理与结果交付 (Post-Process & Delivery) - 路径隔离处理

根据 Router 识别的工具类型，Runtime 采用完全不同的处理逻辑：

**路径 A：Artifact 交付（离线文档模式）**
1.  **代码运行时**：等待 Worker 完整输出。
2.  **后处理 - JSON 格式修复**：
    * 使用 `json_repair` 库对 LLM 输出进行兜底修复
    * 即使 LLM 输出包含 Markdown 标记、多余文本或格式错误，也能自动修复为合法 JSON
    * 修复失败时，返回错误信息并记录日志
    ```python
    # runtime.py 伪代码（路径 A：Artifact 交付）
    # 注意：以下代码为生产环境 Python 版本的实现方案
    import json_repair
    
    def execute_artifact_delivery(tool_name, parameters):
        # 1. 先加载技能模板（提前验证，确定数据需求）
        template = load_template(f"skills/structured/{tool_name}.md")
        # 可选：从模板元数据中提取需要的数据字段列表
        required_fields = extract_data_requirements(template)
        
        # 2. 根据模板需求抓取数据 (MCP)
        raw_data = mcp_client.fetch_data(tool_name, parameters, fields=required_fields)
        
        # 3. 将数据注入模板并调用 LLM
        prompt = inject_data_to_template(template, raw_data)
        response = llm.invoke(
            prompt, 
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # 4. 后处理：JSON 格式修复（兜底机制）
        try:
            # 先尝试标准 JSON 解析
            json_data = json.loads(response)
        except json.JSONDecodeError:
            # 如果失败，使用 json_repair 修复
            try:
                repaired_json = json_repair.repair_json(response)
                json_data = json.loads(repaired_json)
                logger.warning(f"JSON repaired for {tool_name}")
            except Exception as e:
                logger.error(f"JSON repair failed: {e}")
                raise ValueError("无法解析 LLM 输出为有效 JSON")
        
        # 5. 模板引擎 (Jinja2)：将 JSON 数据映射到 HTML 样式模板中
        html_content = jinja2_template.render(json_data)
        
        # 6. PDF 转换器：将 HTML 转换为 PDF 文件
        pdf_path = pdf_renderer.render(html_content)
        
        # 7. 存储文件并返回链接/ID
        file_id = storage.save(pdf_path)
        return {"file_id": file_id, "download_url": f"/api/files/{file_id}"}
    ```
3.  **最终交付**：向用户返回文件 ID 或下载链接。

**路径 B：Interactive 交付（在线对话模式 - Omni Worker）**

#### 生产环境（Python - 计划中）

1.  **代码运行时**：开启流式处理，不等待完整响应。
2.  **Markdown 流式传输**：
    ```python
    # runtime.py 伪代码（路径 B：Interactive 交付）
    # 注意：以下代码为生产环境 Python 版本的实现方案
    def execute_interactive_delivery(tool_name, parameters):
        # 1. 先加载技能模板（Omni Worker 技能）
        template = load_template(f"skills/conversational/{tool_name}.md")
        # 可选：从模板元数据中提取需要的数据字段列表
        required_fields = extract_data_requirements(template)
        
        # 2. 根据模板需求抓取数据 (MCP)
        raw_data = mcp_client.fetch_data(tool_name, parameters, fields=required_fields)
        
        # 3. 将数据注入模板并开启流式输出
        prompt = inject_data_to_template(template, raw_data)
        stream = llm.stream(
            prompt,
            temperature=0.7
        )
        
        # 4. 流式处理并推送（支持分段）
        for chunk in stream:
            # TODO: Markdown 格式修复（待找到合适的库）
            # 当前直接推送，未来可添加 Markdown 格式验证和修复逻辑
            yield chunk  # 实时推送 Markdown 字符到前端
    ```
3.  **前端渲染**：
    * 接收流式 Markdown 文本（通过 SSE/WebSocket）
    * 使用 Markdown 渲染库（如 `react-markdown`, `marked.js`）实时渲染
    * 支持表格、代码块、加粗、列表等格式
    * 可选：识别 Mermaid 语法，渲染流程图/时序图
    * 支持即时追问：用户可在流式输出过程中或完成后继续提问
4.  **最终交付**：用户看到排版精美的实时对话内容，支持打字机效果和即时交互。

#### 当前实现（TypeScript/Cloudflare Workers - Dev/Demo）

**流式传输实现**：

1. **SSE（Server-Sent Events）流式响应**：
   ```typescript
   // handleChatStream 函数实现
   async function handleChatStream(...): Promise<Response> {
     const stream = new ReadableStream({
       async start(controller) {
         const encoder = new TextEncoder();
         const sendEvent = (payload: unknown) => {
           controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
         };
         
         try {
           sendEvent({ type: 'start' });  // 开始事件
           
           const routerResult = await routeRequest(env, content, historyMessages, {
             isStream: true,
           });
           
           // 如果返回的是 ReadableStream（OpenAI 流式响应）
           if (routerResult.content instanceof ReadableStream) {
             await processOpenAIStream(routerResult.content, (delta) => {
               assistantContent += delta;
               sendEvent({ type: 'delta', delta });  // 增量内容事件
             });
           } else {
             // 非流式内容，使用 chunkText 模拟流式效果
             assistantContent = String(routerResult.content);
             const isToolOutput = Boolean(metadata?.tool) && metadata?.tool !== 'consult_omni';
             
             if (!isToolOutput) {
               // 对话内容：分块发送（每块24字符）
               for (const chunk of chunkText(assistantContent)) {
                 sendEvent({ type: 'delta', delta: chunk });
               }
             } else {
               // 工具输出：一次性发送
               sendEvent({ type: 'delta', delta: assistantContent });
             }
           }
           
           sendEvent({ type: 'final', message: finalMessage });  // 完成事件
         } catch (error) {
           sendEvent({ type: 'error', error: errorMessage });  // 错误事件
         } finally {
           controller.enqueue(encoder.encode('data: [DONE]\n\n'));
           controller.close();
         }
       },
     });
     
     return new Response(stream, {
       headers: {
         'Content-Type': 'text/event-stream',
         'Cache-Control': 'no-cache',
         Connection: 'keep-alive',
       },
     });
   }
   ```

2. **OpenAI 流式响应处理**：
   ```typescript
   // processOpenAIStream 函数实现
   async function processOpenAIStream(
     stream: ReadableStream,
     onDelta: (delta: string) => void
   ): Promise<string> {
     const reader = stream.getReader();
     const decoder = new TextDecoder();
     let buffer = '';
     let fullContent = '';
     
     while (true) {
       const { done, value } = await reader.read();
       if (done) break;
       
       buffer += decoder.decode(value, { stream: true });
       const lines = buffer.split('\n');
       buffer = lines.pop() ?? '';
       
       for (const line of lines) {
         const trimmed = line.trim();
         if (trimmed === '' || trimmed === 'data: [DONE]') continue;
         if (trimmed.startsWith('data: ')) {
           const json = JSON.parse(trimmed.slice(6));
           const delta = json.choices?.[0]?.delta?.content;
           if (delta) {
             fullContent += delta;
             onDelta(delta);  // 实时推送增量内容
           }
         }
       }
     }
     return fullContent;
   }
   ```

3. **事件类型**：
   - `start`: 流式传输开始
   - `delta`: 增量内容（Markdown 文本片段）
   - `final`: 传输完成，包含完整消息对象
   - `error`: 错误信息
   - `[DONE]`: 流式传输结束标记

4. **当前限制与实现细节**：
   - ?? ????????????`query_data` ????????????????
     * ???`runWorkerWithTools` ????????????????????
     * ?????????????????/???
   - ? ?? Worker ???????????? OpenAI ????
     * ????? `callOpenAIStreamWithTools` ?? OpenAI Streaming API?`tool_choice: "none"`?
     * ???`processOpenAIStream` ???????????????
   - ✅ SSE 协议已完整实现，支持实时推送和错误处理
     * 事件类型：`start`、`delta`、`final`、`error`、`[DONE]`
     * 错误处理：捕获异常并发送错误事件，同时保存错误消息到数据库

---

## 4. 核心组件定义 (Component Definitions)

### A. 路由智能体 (Router) - 鉴权与分发中心
*   **核心配置**：**工作场景表 (Work Scenario Table)**。这是一个 JSON 列表，定义了 System 的业务边界。
*   **职责**：
    1.  **鉴权 (Gatekeeping)**：检查用户意图是否在“工作场景表”中。不在表中的请求直接拦截。
    2.  **分发 (Dispatching)**：
        *   报表需求 $\rightarrow$ 指派给 Report Worker。
        *   分析需求 $\rightarrow$ 指派给 Omni Worker。
*   **设计原则**：**Strong Router**。Router 是系统的“大脑前叶”，负责所有的决策和过滤，确保下游 Worker 只需要“闭眼干活”。

**工作场景表 Schema（实际数据库结构）**：
```sql
CREATE TABLE IF NOT EXISTS work_scenarios (
  id TEXT PRIMARY KEY,                    -- 场景唯一标识
  name TEXT NOT NULL,                     -- 场景名称
  description TEXT NOT NULL,              -- 场景描述（用于匹配用户意图）
  keywords TEXT,                          -- 关键词列表（JSON数组，可选）
  embedding TEXT,                         -- 向量嵌入（用于相似度匹配，可选）
  enabled INTEGER NOT NULL DEFAULT 1,     -- 是否启用（1=启用，0=禁用）
  created_at TEXT NOT NULL,               -- 创建时间
  updated_at TEXT NOT NULL                -- 更新时间
);
```

**工作场景表示例**：
```json
[
  {
    "id": "generate_driver_report",
    "name": "生成驾驶员安全报告",
    "description": "生成指定司机的安全评估报告，包含风险评分和建议",
    "keywords": ["司机", "驾驶员", "报告", "安全评估"],
    "enabled": 1
  },
  {
    "id": "consult_risk_trend",
    "name": "风险趋势咨询",
    "description": "分析车队近期的风险趋势，解释异常原因",
    "keywords": ["风险", "趋势", "分析"],
    "enabled": 1
  }
]
```

**重要说明**：
- 工作场景表**仅用于接受/拒绝判断**，不再包含 `tool` 和 `required_params` 字段
- 工作场景表只负责接受/拒绝；工具选择由 Router skill 和工具描述共同决定
- 场景匹配支持两种方式：
  - **向量相似度匹配**：使用 `embedding` 字段进行语义相似度搜索
  - **关键词匹配**：使用 `keywords` 字段进行关键词匹配（当前实现中主要用于参考）

### B. Worker Agents (执行层) - 专才与通才

#### 1. Report Worker (路径 A)
*   **角色**：严谨的记录员。
*   **技能来源**：`skills/structured/`
*   **行为**：严格遵循 Schema，输出 JSON。不发散，不聊天。

#### 2. Omni Worker (路径 B)
*   **角色**：资深安全顾问 (Senior Analyst)。
*   **技能来源**：`skills/conversational/`
*   **行为**：
    *   承接 Router 分发的复杂分析任务。
    *   使用 Markdown 格式输出。
    *   可以进行多步推理、数据对比、政策解释。
    *   **注意**：Omni 也是 Worker，它**不负责**判断"接不接活"，只负责"怎么干活"。

#### 3. Rule Reply Worker (路径 B - 规则驱动回复)
*   **角色**：规则执行器，按预配置的规则模板生成标准化回复。
*   **技能来源**：`skills/conversational/rule_reply/`
*   **行为**：
    *   接收 Router 提供的命中规则列表（rule_id + score）。
    *   调用 `get_rule` 工具获取规则详情（包含模板、必需参数、语气要求等）。
    *   检查用户输入是否包含必需参数，缺参时友好追问。
    *   按规则模板生成回复，严格遵循 `must_include` 和 `never_say` 约束。
    *   使用 Markdown 格式流式输出。
*   **特点**：
    *   稳定可控：严格按照规则执行，避免幻觉。
    *   支持缺参追问：自动识别缺失信息并友好询问。
    *   模板填空：将用户输入填充到规则模板中生成自然回复。

### C. MCP 层 (数据工具层) - ToolProvider 抽象设计

**设计目标**：只陈述事实，不发表意见。通过抽象层设计，支持本地实现和未来 MCP 协议集成。

**当前实现（TypeScript/Cloudflare Workers）**：

系统采用 **ToolProvider 抽象层**设计，为未来 MCP 协议集成预留接口：

* **ToolProvider 接口**：
    * `listTools()`: 列出可用工具（对应 MCP `tools/list`）
    * `callTool(name, args)`: 执行工具（对应 MCP `tools/call`）

* **LocalToolProvider（当前实现）**：
    * 直接调用本地函数执行工具
    * 当前实现以下工具：
        * `query_data`: 通用数据查询工具
            * `describe`: 获取数据结构说明（字段定义）
            * `list`: 列出某类型的所有实体（driver/vehicle/route）
            * `get`: 获取单个实体的详细数据
            * `search`: 按关键词搜索实体
        * `get_rule`: 获取规则详情（用于 `rule_reply` Worker）
        * `match_rules`: Rule matching tool (Embedding Service). Runtime runs it before Router and injects results.
            * 对用户查询进行向量化
            * 与规则库进行相似度匹配
            * 返回 topK 匹配结果

* **MCPToolProvider（预留接口）**：
    * 未来可通过 MCP 协议与外部 MCP Server 通信
    * 支持动态工具发现和调用

**关键函数**（当前 LocalToolProvider 实现）：
* `query_data(action, entity_type, ...)`: 通用数据查询工具，返回 SQL/CSV 里的死数据
* 支持实体类型：`driver`（驾驶员）、`vehicle`（车辆）、`route`（线路）
* `get_rule(rule_id)`: 获取规则详情，返回 `rule_json`（包含模板、必需参数等）
* `match_rules(query, top_k, min_score)`: 规则匹配服务，返回 topK 匹配结果

**注意**：这些函数**永远**只返回数据对象，不返回分析文本。

**规则驱动智能体（Rule-Driven Agent）**：
系统支持基于规则的标准化回复，通过 Embedding Service 进行规则匹配：
* **Rule Match**: Runtime ALWAYS runs `match_rules` before Router and injects topK results for Router decision.
* **规则执行**：匹配成功后，Router 派单给 `rule_reply` Worker，按规则模板生成回复
* **规则配置**：支持通过 `rule_asker` 和 `rule_builder` 技能配置和管理规则
* 详细设计参见：`agent/docs/规则列表系统开发文档.md`

**生产环境计划（Python）**：
* 关键函数：
    * `get_driver_metrics(name)`: 返回 SQL/CSV 里的死数据
    * `get_risk_rules()`: 返回静态规则（如"超速阈值=65"）
* 未来将集成 MCP Server，通过标准协议调用数据工具

### C. 技能模板 (Skills / Markdown) - 物理隔离

这是 Worker Agent 的"大脑"，存储为 `.md` 文件。**关键原则：物理隔离，单一职责**。每个技能模板只专注一件事，绝不混合两种输出模式指令。

**设计要点：先加载模板，再查询数据**

系统采用**先加载模板，再查询数据**的执行顺序，原因如下：

1. **提前验证**：模板文件不存在或格式错误时，可立即报错，避免执行无效的数据查询
2. **优化查询**：模板可包含元数据（如 YAML Front Matter），定义需要的数据字段，Runtime 可根据此信息只查询必要数据
3. **依赖关系清晰**：先确定"需要什么"（模板需求），再决定"怎么获取"（数据查询），逻辑更清晰
4. **性能优化**：避免查询不必要的数据字段，减少数据库负载和网络传输

**模板元数据示例**（可选实现）：
```yaml
---
# 技能模板元数据（YAML Front Matter）
data_requirements:
  - driver_id
  - driver_name
  - metrics: [speed_violations, brake_events, accident_history]
  - time_range: 7d
---
[Role] 你是数据处理引擎。
...
```

**路径 A：结构化技能模板（`skills/structured/`）**

这类 Prompt 必须包含**极其严格的格式约束**，专门用于生成机器可解析的 JSON。

* `skill_driver_report_json.md`（司机报告生成）示例：
    ```
    [Role] 你是数据处理引擎。
    [Context] {{driver_data}}
    [Instruction] 分析数据并输出 JSON。
    [Constraint] 
    - **绝对禁止**输出任何 markdown 标记
    - **绝对禁止**输出开场白或解释性文字
    - 仅输出符合以下 Schema 的 JSON 字符串：
    {
      "risk_profile": {...},
      "suggestions": [...],
      "summary": "..."
    }
    ```
    * **人设**：数据处理引擎（非人类语气）。
    * **逻辑**：如果分数 < 60，标记为高危。
    * **槽位**：`{{driver_data}}` 等待 MCP 数据注入。
    * **输出要求**：**必须输出 Strict JSON**，规定最终 JSON 的字段结构。

**路径 B：对话技能模板（`skills/conversational/`）**

这类 Prompt 专注于**排版和语气**，专门用于生成人类友好的 Markdown。

* `skill_driver_consult_md.md`（司机咨询）示例：
    ```
    [Role] 你是贴心的安全顾问。
    [Context] {{driver_data}}
    [Instruction] 请根据数据回答用户疑问。
    [Style] 
    - 使用 **Markdown** 格式
    - 多用列表，关键数字加粗
    - 使用 emoji 缓和语气
    - 直接输出渲染后的文本，无需 JSON 包装
    ```
    * **人设**：贴心的安全顾问（人类友好语气）。
    * **逻辑**：数据统计、趋势分析、异常检测。
    * **输出要求**：**必须输出 Markdown 格式**，不要输出 JSON。

* `skill_query_analysis_md.md`（查询分析）包含：
    * **人设**：数据分析师语气。
    * **输出要求**：使用 Markdown 格式，提供结构化的数据摘要和洞察。

**关键设计原则**：
* ✅ **物理隔离**：技能模板分为两个文件夹，互不干扰
* ✅ **单一职责**：每个模板只包含一种输出格式的指令，不包含 if-else 逻辑
* ✅ **避免混合**：绝不试图写一个万能的 `skill_analysis.md` 来同时支持两种格式

### D. 代码运行时 (Runtime) - 参数隔离执行 + 后处理兜底

> **注意**：以下描述主要针对**生产环境 Python 版本**的实现方案。当前 TypeScript 版本（Dev/Demo）已实现基础功能，但部分高级特性（如 PDF 生成、JSON 修复）待实现。

**路径 A：Artifact 交付（离线模式）**
* **工具**：`pdfkit` 或 `WeasyPrint`（PDF 生成）、`json_repair`（JSON 修复）
* **逻辑**：`LLM 输出` → `JSON 修复（后处理）` → `JSON 数据` + `HTML 模板` = `PDF 文件` → `存储` → `返回链接/ID`
* **特点**：等待完整数据，批量处理，生成静态文件，支持文件存储和下载
* **当前状态**：TypeScript 版本暂未实现 PDF 生成和文件存储，仅返回 JSON 文本

**路径 B：Interactive 交付（在线模式）**
* **工具**：流式 API 调用（如 OpenAI Streaming API）
* **逻辑**：`LLM 流式输出` → `Markdown 修复（后处理，待实现）` → `流式推送（SSE/WS）` → `前端实时渲染`
* **特点**：实时响应，支持分段推送，支持即时追问和多轮对话
* **当前状态**：TypeScript 版本已实现基础流式传输（SSE），Markdown 格式修复待实现

**关键实现要点**：
* **API 参数隔离**：
    * 路径 A：`response_format={"type": "json_object"}` + `temperature=0.1`（API 级别的 JSON 强制约束）
    * 路径 B：`stream=True` + `temperature=0.7`（流式输出，适度高温）
    * **当前状态（TypeScript）**：
        * ⚠️ 路径 A 暂未强制使用 `json_object` 模式（已知限制，依赖 Prompt 约束和 JSON 修复兜底）
        * ✅ 路径 B 已实现流式输出（SSE）
* **技能模板隔离**：根据工具类型，从不同文件夹加载模板（✅ 已实现）
* **后处理机制（兜底）**：
    * **路径 A**：
        * ✅ TypeScript 版本已实现 JSON 格式修复（使用 `json-repair` 库）
        * ✅ 在 `safeJsonParse` 函数中自动修复常见 JSON 格式错误（Markdown 代码块标记、多余逗号、未转义引号等）
        * ✅ 修复失败时返回错误信息
        * ⚠️ PDF 生成和文件存储待实现（Python 版本计划实现）
    * **路径 B**：
        * ⚠️ Markdown 格式修复待实现
        * ✅ 流式推送已实现（SSE）
* **前端集成**：
    * **路径 A**：
        * ✅ 当前接收并显示 JSON 文本（TypeScript 版本）
        * ⚠️ 文件下载/预览功能待实现（Python 版本计划实现）
    * **路径 B**：
        * ✅ 使用 SSE 接收流式数据（TypeScript 版本已实现）
        * ✅ 支持 Markdown 实时渲染（基础功能已实现）
        * ⚠️ Mermaid 图表渲染待实现
        * ✅ 支持即时追问和多轮对话

* **关键点**：这是确定性的代码逻辑，不需要 AI 参与。路径 A 和路径 B 完全解耦，互不干扰。通过**文件隔离**、**调用参数隔离**和**后处理兜底**，确保 JSON 输出的高稳定性，同时保留 Markdown 输出的丰富表现力。

---

## 5. 数据协议 (Data Structures)

### 1. Router 的输出 (内部指令)
```json
{
  "action": "call_tool",
  "tool_name": "fetch_driver_data",
  "parameters": {
    "driver_name": "张三",
    "time_range": "7d"
  }
}

```

### 2. Worker 的输出 (分析结果) - 双轨交付格式

根据任务类型，Worker 输出完全不同的格式，并通过不同的交付方式呈现给用户：

**A 轨：Artifact 交付（Strict JSON → 文件生成）**
```json
{
  "risk_profile": {
    "score": 85,
    "level": "high",
    "factors": [...]
  },
  "suggestions": [
    {"priority": "high", "action": "立即停运整改"},
    {"priority": "medium", "action": "加强培训"}
  ],
  "summary": "张三的风险指数为85分，属于高危级别..."
}
```

**B 轨：Interactive 交付（Markdown → 流式推送） - Omni Worker**

假设用户问："张三最近的数据有什么异常？"

Omni Worker 直接输出 Markdown（无需 JSON 包装），通过流式方式实时推送到前端：
```markdown
### 🚨 风险检测报告：张三

根据最近 7 天的数据分析，我发现以下 **2 项异常**：

1. **急刹车频发**：共发生 **3次**，主要集中在早高峰。
2. **轻微超速**：在 *中山路* 路段检测到一次时速 65km/h。

#### 详细数据表

| 日期 | 时间 | 事件类型 | 数值 |
| :--- | :--- | :--- | :--- |
| 10-01 | 08:30 | 急刹车 | -0.6g |
| 10-02 | 09:15 | 超速 | 65km/h |

💡 **建议**：请车队队长对该司机进行面谈提醒。
```

**双轨交付对比说明**：
* **A 轨 Artifact 交付**：
  * 输出格式：Strict JSON（结构化数据，适合程序处理）
  * 交付方式：生成文件/包（PDF/ZIP/CSV等）→ 存储到服务器 → 返回链接/ID
  * 使用场景：正式报告、批量导出、离线查看
  * 特点：一次性生成，可重复下载，适合存档和分享
  
* **B 轨 Interactive 交付**：
  * 输出格式：Markdown（排版精美、重点突出）
  * 交付方式：流式/分段推送到前端（SSE/WebSocket），支持即时展示与追问
  * 使用场景：实时咨询、交互式问答、探索性分析
  * 特点：实时响应，支持多轮对话，用户体验好

---

## 6. 项目目录结构 (Directory Structure)

### 6.1 生产环境目录结构（Python - 计划中）

```text
/agent
│
├── main.py                # 主程序入口 (宿主程序/大堂)
├── router.py              # 调用 Router LLM 的逻辑
├── config.py              # API Key 配置
│
├── /mcp_tools             # "手脚" (原始数据获取)
│   ├── driver_tools.py    # 获取司机数据的 SQL/CSV 逻辑
│   └── vehicle_tools.py   # 获取车辆数据的逻辑
│
├── /skills                # "菜谱" (Prompt 模板) - 物理隔离
│   ├── router/
│   │   └── SKILL.md       # Router 的 System Prompt
│   │
│   ├── /structured        # 路径 A：结构化技能（JSON 输出）
│   │   ├── generate_driver_report/
│   │   │   └── SKILL.md
│   │   ├── generate_vehicle_report/
│   │   │   └── SKILL.md
│   │   ├── generate_route_report/
│   │   │   └── SKILL.md
│   │   └── ...

│   └── /conversational    # 路径 B：对话技能（Markdown 输出）
│       ├── omni/
│       │   └── SKILL.md
│       └── ...
│       
├── /templates             # "摆盘" (可视化模板)
│   ├── report_style.html  # 用于生成 PDF 的 Jinja2 HTML 模板（A轨）
│   └── logo.png
│
├── /runtime               # 代码运行时（双轨处理逻辑）
│   ├── report_renderer.py # A轨：PDF 渲染器
│   ├── stream_handler.py  # B轨：Markdown 流式处理器
│   └── post_process.py    # 后处理：JSON/Markdown 格式修复
│
├── /storage               # 文件存储（A轨 Artifact）
│   └── artifacts/         # 生成的 PDF/ZIP/CSV 等文件存放目录
│
└── /output                # 生成的 PDF 存放目录（A轨输出，兼容旧路径）
```

### 6.2 当前实现目录结构（TypeScript/Cloudflare Workers - Dev/Demo）

```text
/agent
│
├── src/
│   ├── index.ts           # 主程序入口（Cloudflare Workers）
│   │                       # - Router 逻辑（routeRequest）
│   │                       # - Worker 执行器（runWorkerWithTools）
│   │                       # - ToolProvider 抽象层（LocalToolProvider）
│   │                       # - 流式处理（handleChatStream, processOpenAIStream）
│   │                       # - JSON 修复（safeJsonParse）
│   │                       # - 工作场景表管理
│   │                       # - 会话和消息管理
│   └── api-client.ts      # API 客户端（前端调用）
│
├── skills/                # "菜谱" (Prompt 模板) - 物理隔离
│   ├── router/
│   │   └── SKILL.md       # Router 的 System Prompt
│   │
│   ├── /structured        # 路径 A：结构化技能（JSON 输出）
│   │   ├── generate_driver_report/
│   │   │   └── SKILL.md
│   │   ├── generate_vehicle_report/
│   │   │   └── SKILL.md
│   │   ├── generate_route_report/
│   │   │   └── SKILL.md
│   │   └── ...
│   │
│   └── /conversational    # 路径 B：对话技能（Markdown 输出）
│       ├── omni/
│       │   └── SKILL.md
│       └── ...
│
├── migrations/            # 数据库迁移脚本
│   ├── 0001_init.sql      # 初始化数据库表（sessions, messages, profiles）
│   ├── 0002_work_scenarios.sql  # 工作场景表
│   ├── 0003_seed_agents.sql     # 种子数据（可选）
│   └── ...
│
├── runtime/               # 代码运行时（当前为空，待实现）
│                           # 未来可能包含：
│                           # - PDF 渲染器（Python 版本）
│                           # - 文件存储逻辑（Python 版本）
│
├── wrangler.toml          # Cloudflare Workers 配置
└── tsconfig.json          # TypeScript 配置
```

**说明**：
- 当前 TypeScript 实现主要用于开发和演示
- 技能模板结构已统一，Python 版本可直接复用
- **ToolProvider 抽象层**：已在 `src/index.ts` 中实现，支持未来 MCP 集成
- **JSON 修复**：已在 `safeJsonParse` 函数中实现，使用 `json-repair` 库
- **????**?SSE ???????????? Worker ?????????????
- `/runtime`、`/templates`、`/storage` 等目录在生产环境 Python 版本中实现
- 数据库迁移脚本（SQL）在两个版本中通用


---

## 7. 技能分流策略详解

### 7.1 设计理念：场景门控 + 规则优先路由

**核心变革**：从“场景同时负责鉴权和分流”收敛为“场景做门控，Router 依据规则和工具描述分流”。

**当前方案**：
1.  **用户意图** $\rightarrow$ **工作场景门控**。
2.  **门控通过** $\rightarrow$ **注入规则匹配结果给 Router**。
3.  **Router** $\rightarrow$ **依据规则、skill 和工具描述选择 Worker**。
4.  **门控失败** $\rightarrow$ **直接拒绝服务**。

### 7.2 架构对比：Router vs Omni

我们选择了 **"Strong Router + Specialist Omni"** 的架构：

| 方案 | 描述 | 评价 |
| :--- | :--- | :--- |
| **方案 A (选定)** | **Router** 负责鉴权和分发；**Omni** 只是处理复杂任务的高级 Worker。 | ✅ **职责清晰**：Router 把守大门，Worker 专注执行。维护场景表即可控制业务边界。 |
| **方案 B (弃用)** | **Router** 很弱；**Omni** 是全能上帝，自己决定接不接活、怎么干活。 | ❌ **God Object**：Omni 的 Prompt 会极度复杂，容易产生幻觉，且难以维护。 |

### 7.3 技能分流与单一职责

（保留原有逻辑，仅强调 Omni 是路径 B 的主要执行者）
*   **Report Worker** 专注结构化输出（Path A）。
*   **Omni Worker** 专注交互式分析（Path B）。

### 7.4 实际效果对比

**场景**：用户问"张三最近的数据有什么异常？"

#### 方案一（旧）：强制 JSON 格式（阅读体验差）

```json
{
  "summary": "张三最近有3次急刹车。",
  "details": [
    {"date": "2023-10-01", "event": "急刹车"},
    {"date": "2023-10-02", "event": "超速"}
  ]
}
```

*问题*：用户看到的界面是一堆括号和引号，或者需要后端写死代码去解析它。

#### 方案二（新）：Markdown 格式（阅读体验好）

LLM 直接输出 Markdown（见上方示例），前端实时渲染：
* ✅ 排版精美、重点突出
* ✅ 支持表格、列表、代码块
* ✅ 流式传输，打字机效果
* ✅ 无需后端解析，前端直接渲染

### 7.4 单一职责原则（Single Responsibility Principle）

在设计上必须遵循 **"单一职责原则"**：

1. **Router** 负责分流：在路由时就决定使用哪个技能模板。
2. **Worker (Analysis)** 不再是一个通用的"分析员"，而是根据加载的 Skill 变为：
   * **"数据结构化处理机" (JSON Worker)**：只负责生成 Strict JSON
   * **"交互式咨询师" (Markdown Worker)**：只负责生成 Markdown
3. **技能模板**：每个模板只专注一件事，不包含 if-else 逻辑。
4. **Runtime**：通过文件隔离和调用参数隔离，确保 JSON 输出的 100% 稳定性，同时保留 Markdown 输出的丰富表现力。

### 7.5 技术实现要点

#### 生产环境（Python - 计划中）

**后端（Python Runtime）**：
* 根据 Router 的工具类型，从不同文件夹加载技能模板
* **ToolProvider 抽象层**：
  * 实现 `MCPToolProvider`，通过 MCP 协议调用外部数据服务
  * 支持动态工具发现和调用
* **路径 A（Artifact 交付）**：
  * 使用 `response_format={"type": "json_object"}` 强制 JSON 输出
  * **后处理**：使用 `json_repair` 库进行 JSON 格式修复（兜底机制）
  * 生成文件（PDF/ZIP/CSV等）并存储到服务器
  * 返回文件 ID 或下载链接
* **路径 B（Interactive 交付）**：
  * 使用 `stream=True` 开启流式输出
  * **后处理**：Markdown 格式修复（待实现）
  * 通过 WebSocket 或 SSE 推送到前端
  * 支持分段推送和即时追问

**前端（外包开发）**：
* **A 轨处理**：
  * 接收文件 ID 或下载链接
  * 提供下载按钮或预览功能
* **B 轨处理**：
  * 集成 Markdown 渲染库（`react-markdown`, `marked.js`）
  * 支持 Mermaid 图表渲染（`mermaid.js`）
  * 实现流式接收和实时渲染（打字机效果）
  * 支持即时追问和多轮对话
  * 可选：提取 JSON 块，渲染交互式图表（混合模式进阶方案）

#### 当前实现（TypeScript/Cloudflare Workers - Dev/Demo）

**后端（TypeScript）**：
* ✅ 根据 Router 的工具类型，从不同文件夹加载技能模板（已实现）
* ✅ ToolProvider 抽象层已实现（支持未来 MCP 集成）
* ✅ `query_data` 工具已实现（支持 describe/list/get/search 操作）
* **路径 A（Artifact 交付）**：
  * ⚠️ 暂未强制使用 `response_format={"type": "json_object"}`（已知限制，依赖 Prompt 约束和 JSON 修复兜底）
  * ✅ JSON 格式修复已实现（使用 `json-repair` 库，在 `safeJsonParse` 函数中自动修复）
  * ⚠️ PDF 生成和文件存储待实现
  * ✅ 当前返回 JSON 文本内容（已格式化）
* **路径 B（Interactive 交付）**：
  * ✅ 已实现流式输出（SSE）
  * ⚠️ Markdown 格式修复待实现
  * ✅ 通过 SSE 推送到前端（`handleChatStream` 函数）
  * ✅ 支持分段推送和即时追问
  * ?? ?????????????????????? OpenAI ???????? Worker ????????????? `chunkText` ????

**前端（TypeScript/React - 演示用）**：
* **A 轨处理**：
  * ✅ 接收并显示 JSON 文本（当前实现）
  * ⚠️ 文件下载/预览功能待实现
* **B 轨处理**：
  * ✅ 集成 Markdown 渲染（已实现基础功能）
  * ⚠️ Mermaid 图表渲染待实现
  * ✅ 实现流式接收和实时渲染（打字机效果）
  * ✅ 支持即时追问和多轮对话

### 7.6 后处理机制（Post-Process Safety Net）

**设计理念**：无论 Prompt 如何限制，LLM 的输出仍可能不符合规范。因此需要在 Worker 输出后添加后处理层，作为兜底机制确保系统稳定性。

**A 轨：JSON 格式修复**

**当前实现（TypeScript/Cloudflare Workers）**：
* ✅ **已实现**：使用 `json-repair` 库（npm 包）
* **实现位置**：`safeJsonParse` 函数（`agent/src/index.ts`）
* **功能**：
  * 自动修复常见的 JSON 格式错误（如多余的逗号、未转义的引号等）
  * 移除 LLM 可能添加的 Markdown 标记（如 ```json 代码块标记）
  * 移除开场白或解释性文字
  * 修复不完整的 JSON 结构
  * 兜底机制：如果修复失败，尝试提取 JSON 片段并再次修复
* **实现逻辑**：
  ```typescript
  function safeJsonParse(value: string): unknown | null {
    try {
      // 先尝试标准解析
      return JSON.parse(value);
    } catch {
      try {
        // 使用 json-repair 修复后再解析
        const repaired = repair(value);
        return JSON.parse(repaired);
      } catch (repairError) {
        // 兜底：尝试提取 JSON 片段
        const start = value.indexOf('{');
        const end = value.lastIndexOf('}');
        if (start !== -1 && end !== -1 && end > start) {
          const snippet = value.slice(start, end + 1);
          const repairedSnippet = repair(snippet);
          return JSON.parse(repairedSnippet);
        }
        return null;
      }
    }
  }
  ```
* **失败处理**：如果修复失败，返回 `null`，上层调用会返回错误信息给用户

**生产环境计划（Python）**：
* **工具**：`json_repair` 库（Python）
* **实现示例**：
  ```python
  import json_repair
  
  def repair_json_output(llm_response: str) -> dict:
      try:
          # 先尝试标准解析
          return json.loads(llm_response)
      except json.JSONDecodeError:
          # 使用 json_repair 修复
          repaired = json_repair.repair_json(llm_response)
          return json.loads(repaired)
  ```
* **失败处理**：如果修复失败，记录错误日志并返回明确的错误信息给用户

**B 轨：Markdown 格式修复**
* **状态**：待实现（当前留空）
* **需求**：
  * 验证 Markdown 语法正确性
  * 修复常见的格式错误（如表格对齐、代码块闭合等）
  * 确保输出符合 Markdown 规范
* **潜在方案**（待调研）：
  * 使用 Markdown 解析库（如 `markdown`、`mistune`）进行验证
  * 自定义修复逻辑处理常见错误
  * 或使用专门的 Markdown 修复工具（如存在）

**关键原则**：
* ✅ **兜底而非依赖**：后处理是最后一道防线，不能替代良好的 Prompt 设计
* ✅ **透明性**：修复过程应记录日志，便于调试和优化
* ✅ **优雅降级**：修复失败时应返回清晰的错误信息，而非崩溃

---

## 8. 未来规划 (Roadmap)

1. **多轮对话记忆 (Memory)**：引入 Redis，当用户在生成报告后追问"他上次事故是什么时候？"时，系统能通过历史上下文回答。
2. **人工审核 (Human-in-the-Loop)**：在生成 PDF 之前，先将 JSON 摘要展示给用户，用户确认无误后再渲染文件。
3. **批量处理 (Batch Processing)**：增加定时任务（Cron Job），每周一凌晨自动遍历所有司机，批量生成报告。
4. **实时风险预警**：扩展系统功能，支持实时监控和主动预警，当检测到高风险事件时主动通知用户。
5. **智能问答增强**：支持更丰富的安全咨询功能，如"如何降低某路线的安全事故率？"等复杂问题。
6. **多模态交互**：支持语音输入、图表可视化、交互式数据探索等多种交互方式。
