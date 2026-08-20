import { config } from '../config';
import { kbRepository } from '../db/repository';
import { generateEmbedding } from './embedding';
import { buildEmbeddingText } from './document-parser';
import { deleteClausePointsByKey, ensureQdrantCollection, makePointId, upsertClausePoint } from './qdrant';

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nextRetryAt(retryCount: number): string {
  const backoffSeconds = Math.min(300, Math.pow(2, retryCount) * 5);
  return new Date(Date.now() + backoffSeconds * 1000).toISOString();
}

async function processUpsertJob(job: {
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
}): Promise<void> {
  const clause = await kbRepository.getClauseForIndexing(job.tenant_id, job.kb_id, job.doc_id, job.clause_id);
  if (!clause || clause.is_deleted === 1 || clause.status !== 'active') {
    await deleteClausePointsByKey(job);
    return;
  }
  const vector = await generateEmbedding(buildEmbeddingText(clause.title, clause.field_path, clause.content_text));
  await deleteClausePointsByKey(job);
  await upsertClausePoint({
    point_id: makePointId({
      tenant_id: clause.tenant_id,
      kb_id: clause.kb_id,
      doc_id: clause.doc_id,
      clause_id: clause.clause_id,
      version: clause.version,
    }),
    vector,
    payload: {
      tenant_id: clause.tenant_id,
      kb_id: clause.kb_id,
      doc_id: clause.doc_id,
      clause_id: clause.clause_id,
      field_path: clause.field_path,
      min_level: clause.min_level,
      min_rank: clause.min_rank,
      doc_version: 0,
      clause_version: clause.version,
      is_deleted: false,
      status: clause.status,
      tags: kbRepository.parseTags(clause.tags_json),
      updated_at: clause.updated_at,
    },
  });
  await kbRepository.duplicateClauseWithVectorState(clause, 'ready', '');
}

async function processDeleteJob(job: {
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
}): Promise<void> {
  await deleteClausePointsByKey(job);
  const clause = await kbRepository.getClauseById(job.tenant_id, job.kb_id, job.doc_id, job.clause_id);
  if (clause) {
    await kbRepository.duplicateClauseWithVectorState(clause, 'deleted', '');
  }
}

async function processJobByType(job: {
  job_type: 'upsert' | 'delete' | 'rebuild';
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
}): Promise<void> {
  if (job.job_type === 'upsert') {
    await processUpsertJob(job);
    return;
  }
  if (job.job_type === 'delete') {
    await processDeleteJob(job);
    return;
  }
  if (job.job_type === 'rebuild') {
    await processUpsertJob(job);
  }
}

async function processOne(job: Awaited<ReturnType<typeof kbRepository.listRunnableJobs>>[number]): Promise<void> {
  const running = await kbRepository.appendJobRevision(job, {
    status: 'running',
    last_error: '',
  });
  try {
    await processJobByType({
      job_type: running.job_type,
      tenant_id: running.tenant_id,
      kb_id: running.kb_id,
      doc_id: running.doc_id,
      clause_id: running.clause_id,
    });
    await kbRepository.appendJobRevision(running, {
      status: 'success',
      next_run_at: new Date().toISOString(),
      last_error: '',
    });
  } catch (error) {
    const retryCount = running.retry_count + 1;
    const message = error instanceof Error ? error.message : String(error);
    const terminal = retryCount > config.indexJobMaxRetry;
    await kbRepository.appendJobRevision(running, {
      status: 'failed',
      retry_count: retryCount,
      last_error: message.slice(0, 1000),
      next_run_at: terminal ? '9999-12-31T00:00:00.000Z' : nextRetryAt(retryCount),
    });
    if (terminal) {
      const clause = await kbRepository.getClauseById(running.tenant_id, running.kb_id, running.doc_id, running.clause_id);
      if (clause) {
        await kbRepository.duplicateClauseWithVectorState(clause, 'failed', message.slice(0, 1000));
      }
    }
  }
}

export async function runOneWorkerTick(): Promise<number> {
  const jobs = await kbRepository.listRunnableJobs(config.indexWorkerBatchSize);
  if (!jobs.length) return 0;

  const concurrency = Math.max(1, config.indexWorkerConcurrency);
  for (let i = 0; i < jobs.length; i += concurrency) {
    const chunk = jobs.slice(i, i + concurrency);
    await Promise.all(chunk.map((job) => processOne(job)));
  }
  return jobs.length;
}

export async function runWorkerLoop(): Promise<void> {
  await ensureQdrantCollection();
  for (;;) {
    const processed = await runOneWorkerTick();
    if (processed === 0) {
      await delay(config.indexJobPollIntervalMs);
    }
  }
}
