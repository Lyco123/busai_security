export type SessionRunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
export type SessionRunMode = 'chat' | 'stream';

export interface SessionRunRecord {
  id: string;
  session_id: string;
  status: SessionRunStatus;
  mode: SessionRunMode;
  request_content: string;
  request_metadata: string | null;
  response_json: string | null;
  error_message: string | null;
  superseded_by_run_id: string | null;
  cancel_requested: number;
  lease_owner: string | null;
  lease_expires_at: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

interface D1PreparedStatementLike {
  bind: (...values: unknown[]) => D1PreparedStatementLike;
  first: <T = Record<string, unknown>>() => Promise<T | null>;
  all: <T = Record<string, unknown>>() => Promise<{ results: T[] }>;
  run: () => Promise<unknown>;
}

interface D1DatabaseLike {
  prepare: (query: string) => D1PreparedStatementLike;
}

export interface CreateSessionRunInput {
  id: string;
  sessionId: string;
  mode: SessionRunMode;
  content: string;
  metadata?: Record<string, unknown>;
}

export function createSessionRunRepository() {
  async function createQueuedRun(
    db: D1DatabaseLike,
    input: CreateSessionRunInput
  ): Promise<SessionRunRecord> {
    const now = new Date().toISOString();
    const metadataJson = input.metadata ? JSON.stringify(input.metadata) : null;

    await cancelQueuedRuns(db, input.sessionId, input.id, now, 'Superseded by a newer request.');

    try {
      await insertQueuedRun(db, input, metadataJson, now);
    } catch (error) {
      await cancelQueuedRuns(db, input.sessionId, input.id, now, 'Superseded by a newer request.');
      try {
        await insertQueuedRun(db, input, metadataJson, now);
      } catch {
        throw error;
      }
    }

    const run = await getRun(db, input.id);
    if (!run) {
      throw new Error('Failed to create session run.');
    }
    return run;
  }

  async function insertQueuedRun(
    db: D1DatabaseLike,
    input: CreateSessionRunInput,
    metadataJson: string | null,
    now: string
  ): Promise<void> {
    await db
      .prepare(
        `INSERT INTO session_runs (
          id,
          session_id,
          status,
          mode,
          request_content,
          request_metadata,
          created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)`
      )
      .bind(input.id, input.sessionId, 'queued', input.mode, input.content, metadataJson, now)
      .run();
  }

  async function cancelQueuedRuns(
    db: D1DatabaseLike,
    sessionId: string,
    supersededByRunId: string,
    finishedAt: string,
    reason: string
  ): Promise<void> {
    const responseJson = JSON.stringify({
      role: 'assistant',
      content: 'This request was replaced by a newer message.',
      metadata: {
        session_run_status: 'cancelled',
        superseded_by_run_id: supersededByRunId,
      },
      tools: [],
    });

    await db
      .prepare(
        `UPDATE session_runs
         SET status = ?,
             superseded_by_run_id = ?,
             error_message = ?,
             response_json = ?,
             finished_at = ?
         WHERE session_id = ? AND status = ?`
      )
      .bind('cancelled', supersededByRunId, reason, responseJson, finishedAt, sessionId, 'queued')
      .run();
  }

  async function expireStaleRunningRuns(
    db: D1DatabaseLike,
    now: string,
    staleStartedBefore: string
  ): Promise<void> {
    await db
      .prepare(
        `UPDATE session_runs
         SET status = ?,
             error_message = ?,
             finished_at = ?
         WHERE status = ?
           AND (
             (lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
             OR (started_at IS NOT NULL AND started_at <= ?)
           )`
      )
      .bind(
        'failed',
        'Run lease expired or became stale before completion.',
        now,
        'running',
        now,
        staleStartedBefore
      )
      .run();
  }

  async function tryStartRun(
    db: D1DatabaseLike,
    runId: string,
    leaseOwner: string,
    leaseExpiresAt: string,
    staleStartedBefore: string
  ): Promise<SessionRunRecord | null> {
    const now = new Date().toISOString();
    await expireStaleRunningRuns(db, now, staleStartedBefore);

    await db
      .prepare(
        `UPDATE session_runs
         SET status = ?,
             lease_owner = ?,
             lease_expires_at = ?,
             started_at = ?,
             error_message = NULL
         WHERE id = ?
           AND status = ?
           AND NOT EXISTS (
             SELECT 1
             FROM session_runs active
             WHERE active.session_id = session_runs.session_id
               AND active.status = ?
               AND active.lease_expires_at > ?
           )`
      )
      .bind('running', leaseOwner, leaseExpiresAt, now, runId, 'queued', 'running', now)
      .run();

    const run = await getRun(db, runId);
    if (run?.status === 'running' && run.lease_owner === leaseOwner) {
      return run;
    }
    return null;
  }

  async function completeRun(
    db: D1DatabaseLike,
    runId: string,
    response: Record<string, unknown>
  ): Promise<void> {
    const now = new Date().toISOString();
    await db
      .prepare(
        `UPDATE session_runs
         SET status = ?,
             response_json = ?,
             finished_at = ?
         WHERE id = ? AND status = ?`
      )
      .bind('completed', JSON.stringify(response), now, runId, 'running')
      .run();
  }

  async function failRun(db: D1DatabaseLike, runId: string, errorMessage: string): Promise<void> {
    const now = new Date().toISOString();
    await db
      .prepare(
        `UPDATE session_runs
         SET status = ?,
             error_message = ?,
             finished_at = ?
         WHERE id = ? AND status IN (?, ?)`
      )
      .bind('failed', errorMessage, now, runId, 'running', 'queued')
      .run();
  }

  async function getRun(db: D1DatabaseLike, runId: string): Promise<SessionRunRecord | null> {
    return db
      .prepare(
        `SELECT
          id,
          session_id,
          status,
          mode,
          request_content,
          request_metadata,
          response_json,
          error_message,
          superseded_by_run_id,
          cancel_requested,
          lease_owner,
          lease_expires_at,
          created_at,
          started_at,
          finished_at
        FROM session_runs
        WHERE id = ?`
      )
      .bind(runId)
      .first<SessionRunRecord>();
  }

  async function isRunRunning(db: D1DatabaseLike, runId: string): Promise<boolean> {
    const row = await db
      .prepare('SELECT status FROM session_runs WHERE id = ?')
      .bind(runId)
      .first<{ status: string }>();
    return row?.status === 'running';
  }

  return {
    createQueuedRun,
    tryStartRun,
    completeRun,
    failRun,
    getRun,
    isRunRunning,
  };
}
