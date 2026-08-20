import { config } from './config';
import { runWorkerLoop } from './services/job-worker';
import { ensureQdrantCollection } from './services/qdrant';

async function bootstrap() {
  await ensureQdrantCollection();
  // eslint-disable-next-line no-console
  console.log(`[kb-worker] started with poll interval ${config.indexJobPollIntervalMs}ms`);
  await runWorkerLoop();
}

bootstrap().catch((error) => {
  // eslint-disable-next-line no-console
  console.error('[kb-worker] fatal error', error);
  process.exit(1);
});
