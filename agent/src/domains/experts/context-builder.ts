import { buildOmniKbRuntimeOptions } from '../chat/omni-kb-context';
import type { HistoryMessage } from '../chat/context';
import type { WorkerRuntimeOptions, WorkerToolName } from '../chat/worker-runner';
import { getExpertRegistryItemByWorkerTool } from './registry';

interface BuildExpertRuntimeContextParams {
  workerTool: WorkerToolName;
  userQuery: string;
  historyMessages?: HistoryMessage[];
  baseRuntimeOptions?: WorkerRuntimeOptions;
}

interface ExpertRuntimeEnv {
  KB_API_BASE_URL?: string;
  KB_API_TIMEOUT_MS?: string;
  KB_DEFAULT_ID?: string;
  KB_TENANT_ID?: string;
}

export async function buildExpertRuntimeContext(
  env: ExpertRuntimeEnv,
  params: BuildExpertRuntimeContextParams
): Promise<WorkerRuntimeOptions | undefined> {
  const registryItem = getExpertRegistryItemByWorkerTool(params.workerTool);
  let runtimeOptions = params.baseRuntimeOptions;

  if (params.workerTool === 'consult_omni' || registryItem?.taskType === 'consult') {
    runtimeOptions = await buildOmniKbRuntimeOptions(env, params.userQuery, runtimeOptions);
  }

  if (!registryItem) {
    return runtimeOptions;
  }

  return {
    ...(runtimeOptions ?? {}),
    metadata: {
      ...(runtimeOptions?.metadata ?? {}),
      expert_runtime: {
        domain: registryItem.domain,
        task_type: registryItem.taskType,
        worker_tool: registryItem.workerTool,
        context_flags: registryItem.contextFlags,
        history_message_count: Array.isArray(params.historyMessages) ? params.historyMessages.length : 0,
      },
    },
  };
}
