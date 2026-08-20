import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoDir = path.resolve(scriptDir, '..');
const outDir = path.join(repoDir, '.tmp-report-output-format-contract');

function run(command, args) {
  execFileSync(command, args, {
    cwd: repoDir,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
}

function cleanup() {
  rmSync(outDir, { recursive: true, force: true });
}

function createStructuredReportJson() {
  return JSON.stringify(
    {
      report_type: 'vehicle_safety_summary_management',
      layout: {
        title: 'Vehicle Risk Summary',
        summary: 'Vehicle risk remains within target.',
        sections: [],
      },
    },
    null,
    2
  );
}

function createDeps(routeMetadata, routeParts = {}) {
  const routeCalls = [];
  return {
    routeCalls,
    TOOL_OUTPUT_PREVIEW_CHARS: 200,
    createId: (prefix) => `${prefix}-1`,
    getHistoryMessages: async () => [],
    saveMessage: async () => undefined,
    updateSessionPreview: async () => undefined,
    createTurnContext: async () => ({
      routingMode: 'router_decide',
      variantContext: null,
    }),
    tryHandleRuleConfig: async () => null,
    routeRequest: async (_env, _content, _historyMessages, options) => {
      routeCalls.push(options);
      return {
        content: createStructuredReportJson(),
        metadata: routeMetadata,
        ...routeParts,
      };
    },
    decorateAssistantMetadata: (_turnContext, metadata) => metadata ?? {},
    hasDecoratedAssistantMetadata: () => false,
    maybeGenerateSessionTitle: async () => undefined,
    scheduleSessionTitleGeneration: () => undefined,
  };
}

cleanup();
try {
  run('npx', [
    'tsc',
    '--target',
    'es2020',
    '--module',
    'commonjs',
    '--outDir',
    outDir,
    'src/domains/chat/chat-service.ts',
  ]);

  const compiled = await import(
    pathToFileURL(path.join(outDir, 'domains', 'chat', 'chat-service.js')).href
  );

  const markdownDeps = createDeps(undefined, {
    leadingContent: 'Preparing report...\n\n',
    trailingContent: '\n\nReport ready.',
  });
  const markdownService = compiled.createChatService(markdownDeps);
  const markdownReply = await markdownService.handleReportSummary(
    { OUTPUT_FORMAT: 'markdown' },
    { type: 'vehicle', nameOrId: 'vehicle-02650' }
  );
  assert.equal(markdownDeps.routeCalls[0]?.suppressStageText, true);
  assert.match(markdownReply.content, /^## Vehicle Risk Summary/m);
  assert.doesNotMatch(markdownReply.content, /Preparing report/);
  assert.doesNotMatch(markdownReply.content, /Report ready/);
  assert.doesNotMatch(markdownReply.content, /"report_type"/);
  assert.equal(markdownReply.metadata.tool, 'generate_vehicle_report');

  const jsonService = compiled.createChatService(createDeps({ tool: 'generate_vehicle_report' }));
  const jsonReply = await jsonService.handleReportSummary(
    { OUTPUT_FORMAT: 'json' },
    { type: 'vehicle', nameOrId: 'vehicle-02650' }
  );
  assert.equal(jsonReply.content, createStructuredReportJson());
  assert.equal(jsonReply.metadata.tool, 'generate_vehicle_report');

  console.log('report output format contract passed');
} finally {
  cleanup();
}
