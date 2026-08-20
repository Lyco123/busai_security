# 专家体系架构与设计

日期：2026-04-18

## 1. 范围

本方案面向当前 5 个专家/报告 domain：

- 驾驶员
- 车辆
- 单位
- 线路
- 事故

本方案只定义：

- 运行时结构
- expert 配置结构
- 上下文注入结构
- 与现有代码的落地接口

## 2. 目标架构

```text
User
  -> Router
  -> tool choice
  -> Expert Registry
  -> Shared Context Builder
  -> Worker Runner
  -> Output
```

保留现有：

- router 决策
- worker-runner 执行
- 现有 `SKILL.md`
- 现有报告 worker 逻辑

新增：

- `Expert Registry`
- `Shared Context Builder`

## 3. 运行时分层

### 3.1 Router

职责：

- 决定当前请求进入哪类工具
- 区分：
  - `generate_*_report`
  - `consult_*`
  - `rule_reply`
  - `request_further_info`

当前代码入口：

- [router-service.ts](/d:/BUS/agent/src/domains/chat/router-service.ts)

### 3.2 Expert Registry

职责：

- 集中保存 domain expert / report worker 的静态配置
- 提供 worker 执行所需的统一查表入口

建议新增：

- `agent/src/domains/experts/registry.ts`

### 3.3 Shared Context Builder

职责：

- 根据 expert 配置拼装运行时额外上下文
- 统一处理 report source / KB / 最近报告 / 待澄清状态

建议新增：

- `agent/src/domains/experts/context-builder.ts`

### 3.4 Worker Runner

职责：

- 加载 skill
- 调用工具
- 处理开场/收尾
- 记录 metadata

当前代码入口：

- [worker-runner.ts](/d:/BUS/agent/src/domains/chat/worker-runner.ts)

## 4. Expert Registry 设计

### 4.1 文件位置

- `agent/src/domains/experts/registry.ts`

### 4.2 类型定义

```ts
export type ExpertDomain =
  | 'driver'
  | 'vehicle'
  | 'unit'
  | 'route'
  | 'incident';

export type ExpertTaskType =
  | 'consult'
  | 'report';

export interface ExpertContextFlags {
  profile?: boolean;
  kb?: boolean;
  latestReport?: boolean;
  pendingClarification?: boolean;
}

export interface ExpertRegistryItem {
  domain: ExpertDomain;
  taskType: ExpertTaskType;
  workerTool: string;
  skillKey: string;
  supportsDeepCot?: boolean;
  deepCotSystemPrompt?: string;
  contextFlags: ExpertContextFlags;
}
```

### 4.3 初始注册项

建议至少注册：

- `driver + consult`
- `driver + report`
- `vehicle + consult`
- `vehicle + report`
- `unit + report`
- `route + report`
- `incident + report`

后续可继续加：

- `unit + consult`
- `route + consult`
- `incident + consult`

### 4.4 查询接口

```ts
export function getExpertRegistryItem(
  domain: ExpertDomain,
  taskType: ExpertTaskType
): ExpertRegistryItem | null
```

## 5. Shared Context Builder 设计

### 5.1 文件位置

- `agent/src/domains/experts/context-builder.ts`

### 5.2 输入接口

```ts
export interface BuildExpertRuntimeContextParams {
  workerTool: string;
  domain: ExpertDomain;
  taskType: ExpertTaskType;
  userQuery: string;
  historyMessages: Array<{ role: string; content: string }>;
  baseRuntimeOptions?: WorkerRuntimeOptions;
}
```

### 5.3 输出接口

```ts
export async function buildExpertRuntimeContext(
  env: Env,
  params: BuildExpertRuntimeContextParams
): Promise<WorkerRuntimeOptions | undefined>
```

### 5.4 第一版支持的上下文类型

#### A. Profile / Report Source

适用：

- 报告 worker

复用来源：

- [structured-report-data-sources.ts](/d:/BUS/agent/src/domains/chat/structured-report-data-sources.ts)

#### B. KB

适用：

- `consult_omni`
- 后续可扩展给特定 expert

复用来源：

- [omni-kb-context.ts](/d:/BUS/agent/src/domains/chat/omni-kb-context.ts)

#### C. Latest Structured Report

适用：

- 报告追问
- expert 对最近报告的追问

复用来源：

- session routing context 相关逻辑

#### D. Pending Clarification

适用：

- 补参数
- 延续澄清流程

复用来源：

- clarification state 相关逻辑

### 5.5 上下文拼装顺序

建议顺序：

1. `baseRuntimeOptions`
2. deep COT system prompt
3. latest report / clarification
4. profile/report source
5. KB
6. metadata merge

## 6. skill 设计边界

### 6.1 继续保留现有 skill 文件

现有目录保持不变：

- `agent/skills/conversational/*`
- `agent/skills/structured/*`

### 6.2 skill 中保留的内容

- 角色
- 职责边界
- 回答风格
- 输出结构
- 深度策略

### 6.3 不放在 skill 中的内容

- 动态上下文来源
- 实验开关
- 会话恢复逻辑
- 运行时注入细节

这些统一由 registry 和 context builder 处理。

## 7. deep COT 设计

### 7.1 配置位置

deep COT 相关配置进入 registry：

- `supportsDeepCot`
- `deepCotSystemPrompt`

### 7.2 运行时判断

统一在 context builder 或单独 helper 中判断：

- 当前是否 `deep`
- 当前 expert 是否支持 deep
- 是否还存在实验 gate

### 7.3 接口建议

```ts
export function resolveDeepCotRuntimeOptions(
  item: ExpertRegistryItem,
  params: {
    cotMode?: string | null;
    turnContext?: ChatTurnContext | null;
  }
): WorkerRuntimeOptions | undefined
```

## 8. 与现有代码的衔接

### 8.1 `runtime.ts`

当前入口：

- [runtime.ts](/d:/BUS/agent/src/app/runtime.ts)

建议改动：

- 引入 registry
- 引入 context builder
- 不再在 runtime 中分散写 expert 特判

### 8.2 `router-service.ts`

当前入口：

- [router-service.ts](/d:/BUS/agent/src/domains/chat/router-service.ts)

建议改动：

- 主体逻辑不动
- 在选中 `consult_*_expert` 或 `generate_*_report` 后，通过 registry 和 context builder 组装运行时配置

### 8.3 `worker-runner.ts`

当前入口：

- [worker-runner.ts](/d:/BUS/agent/src/domains/chat/worker-runner.ts)

建议改动：

- 主体逻辑不动
- 继续接受 `runtimeOptions`

## 9. 最小落地步骤

### Phase 1

新增两个文件：

- `agent/src/domains/experts/registry.ts`
- `agent/src/domains/experts/context-builder.ts`

### Phase 2

在 `runtime.ts` 中接入：

- registry 查表
- context builder 拼装 `runtimeOptions`

### Phase 3

把以下现有逻辑逐步迁入 context builder：

- `omni-kb-context.ts`
- `structured-report-data-sources.ts` 中的运行时注入部分
- latest structured report / pending clarification 注入部分

## 10. 元数据建议

建议统一补充以下 metadata：

- `domain`
- `task_type`
- `worker_tool`
- `skill_key`
- `context_flags`
- `cot_mode`
- `cot_enabled`

## 11. 文件清单

### 新增

- `agent/src/domains/experts/registry.ts`
- `agent/src/domains/experts/context-builder.ts`

### 主要接入点

- [runtime.ts](/d:/BUS/agent/src/app/runtime.ts)
- [router-service.ts](/d:/BUS/agent/src/domains/chat/router-service.ts)
- [worker-runner.ts](/d:/BUS/agent/src/domains/chat/worker-runner.ts)

