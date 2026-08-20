import { safeJsonParse } from '../../shared/json';

type AgentRole = 'user' | 'assistant' | 'system' | 'tool';

export interface AgentMessage {
  id: string;
  role: AgentRole;
  content: string;
  createdAt: string;
  status?: 'complete' | 'error';
  sources?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

export interface AgentSession {
  id: string;
  title: string;
  preview: string;
  updatedAt: string;
}

export interface AgentSessionDetail extends AgentSession {
  messages: AgentMessage[];
}

export interface AgentSessionMeta {
  id: string;
  title: string;
  updatedAt: string;
}

export interface SessionAuthContext {
  role: string;
  principal_id: string;
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

export interface SessionMessageInput {
  id: string;
  role: AgentRole;
  content: string;
  status?: 'complete' | 'error';
  sources?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

export function createSessionRepository(options: {
  createId: (prefix: string) => string;
}) {
  async function listAgentSessions(
    db: D1DatabaseLike,
    auth: SessionAuthContext,
    options?: { includeRuleConfig?: boolean }
  ): Promise<AgentSession[]> {
    const includeRuleConfig = options?.includeRuleConfig ?? false;
    const conditions: string[] = [];
    const params: unknown[] = [];
    let query = 'SELECT s.id, s.title, s.preview, s.updated_at FROM agent_sessions s';

    if (!includeRuleConfig) {
      query += ' LEFT JOIN rule_drafts d ON d.session_id = s.id';
      conditions.push('d.session_id IS NULL');
    }
    if (auth.role !== 'admin') {
      conditions.push('s.owner_id = ?');
      params.push(auth.principal_id);
    }
    if (conditions.length > 0) {
      query += ` WHERE ${conditions.join(' AND ')}`;
    }
    query += ' ORDER BY s.updated_at DESC';

    const result = await db
      .prepare(query)
      .bind(...params)
      .all<{ id: string; title: string; preview: string | null; updated_at: string }>();

    return result.results.map((row) => ({
      id: row.id,
      title: row.title,
      preview: row.preview || '',
      updatedAt: row.updated_at,
    }));
  }

  async function getAgentSession(
    db: D1DatabaseLike,
    sessionId: string,
    auth?: SessionAuthContext
  ): Promise<AgentSessionDetail | null> {
    const sessionRow = await db
      .prepare('SELECT id, title, preview, updated_at, owner_id FROM agent_sessions WHERE id = ?')
      .bind(sessionId)
      .first<{ id: string; title: string; preview: string | null; updated_at: string; owner_id: string | null }>();

    if (!sessionRow) {
      return null;
    }
    if (auth && auth.role !== 'admin' && sessionRow.owner_id !== auth.principal_id) {
      return null;
    }

    let messagesResult:
      | {
          results: Array<{
            id: string;
            role: string;
            content: string;
            created_at: string;
            status: string | null;
            sources_json?: string | null;
            metadata: string | null;
          }>;
        }
      | {
          results: Array<{
            id: string;
            role: string;
            content: string;
            created_at: string;
            status: string | null;
            metadata: string | null;
          }>;
        };

    try {
      messagesResult = await db
        .prepare(
          'SELECT id, role, content, created_at, status, sources_json, metadata FROM agent_messages WHERE session_id = ? ORDER BY created_at ASC'
        )
        .bind(sessionId)
        .all();
    } catch {
      messagesResult = await db
        .prepare(
          'SELECT id, role, content, created_at, status, metadata FROM agent_messages WHERE session_id = ? ORDER BY created_at ASC'
        )
        .bind(sessionId)
        .all();
    }

    const messages: AgentMessage[] = messagesResult.results.map((row: {
      id: string;
      role: string;
      content: string;
      created_at: string;
      status: string | null;
      sources_json?: string | null;
      metadata: string | null;
    }) => {
      const message: AgentMessage = {
        id: row.id,
        role: row.role as AgentRole,
        content: row.content,
        createdAt: row.created_at,
      };

      if (row.status) {
        message.status = row.status as 'complete' | 'error';
      }
      if (row.sources_json) {
        const parsed = safeJsonParse(row.sources_json);
        if (Array.isArray(parsed)) {
          message.sources = parsed.filter(
            (item): item is Record<string, unknown> =>
              Boolean(item) && typeof item === 'object' && !Array.isArray(item)
          );
        }
      }
      if (row.metadata) {
        const parsed = safeJsonParse(row.metadata);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          message.metadata = parsed as Record<string, unknown>;
        }
      }

      return message;
    });

    return {
      id: sessionRow.id,
      title: sessionRow.title,
      preview: sessionRow.preview || '',
      updatedAt: sessionRow.updated_at,
      messages,
    };
  }

  async function getAgentSessionMeta(
    db: D1DatabaseLike,
    sessionId: string,
    auth?: SessionAuthContext
  ): Promise<AgentSessionMeta | null> {
    const sessionRow = await db
      .prepare('SELECT id, title, updated_at, owner_id FROM agent_sessions WHERE id = ?')
      .bind(sessionId)
      .first<{ id: string; title: string; updated_at: string; owner_id: string | null }>();

    if (!sessionRow) {
      return null;
    }
    if (auth && auth.role !== 'admin' && sessionRow.owner_id !== auth.principal_id) {
      return null;
    }

    return {
      id: sessionRow.id,
      title: sessionRow.title,
      updatedAt: sessionRow.updated_at,
    };
  }

  async function createAgentSession(
    db: D1DatabaseLike,
    title: string,
    ownerId: string
  ): Promise<AgentSessionDetail> {
    const sessionId = options.createId('session');
    const now = new Date().toISOString();

    await db
      .prepare(
        'INSERT INTO agent_sessions (id, title, preview, created_at, updated_at, owner_id) VALUES (?, ?, ?, ?, ?, ?)'
      )
      .bind(sessionId, title, '', now, now, ownerId)
      .run();

    return {
      id: sessionId,
      title,
      preview: '',
      updatedAt: now,
      messages: [],
    };
  }

  async function deleteAgentSession(db: D1DatabaseLike, sessionId: string): Promise<boolean> {
    await db.prepare('DELETE FROM session_runs WHERE session_id = ?').bind(sessionId).run();
    await db.prepare('DELETE FROM agent_messages WHERE session_id = ?').bind(sessionId).run();
    await db.prepare('DELETE FROM rule_drafts WHERE session_id = ?').bind(sessionId).run();
    await db.prepare('DELETE FROM agent_sessions WHERE id = ?').bind(sessionId).run();
    return true;
  }

  async function saveMessage(
    db: D1DatabaseLike,
    sessionId: string,
    message: SessionMessageInput
  ): Promise<void> {
    const now = new Date().toISOString();
    const sourcesJson = Array.isArray(message.sources) ? JSON.stringify(message.sources) : null;
    const metadataJson = message.metadata ? JSON.stringify(message.metadata) : null;

    try {
      await db
        .prepare(
          'INSERT INTO agent_messages (id, session_id, role, content, created_at, status, sources_json, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        )
        .bind(
          message.id,
          sessionId,
          message.role,
          message.content,
          now,
          message.status || null,
          sourcesJson,
          metadataJson
        )
        .run();
    } catch {
      await db
        .prepare(
          'INSERT INTO agent_messages (id, session_id, role, content, created_at, status, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)'
        )
        .bind(
          message.id,
          sessionId,
          message.role,
          message.content,
          now,
          message.status || null,
          metadataJson
        )
        .run();
    }
  }

  async function updateSessionPreview(
    db: D1DatabaseLike,
    sessionId: string,
    preview: string
  ): Promise<void> {
    const now = new Date().toISOString();
    await db
      .prepare('UPDATE agent_sessions SET preview = ?, updated_at = ? WHERE id = ?')
      .bind(preview, now, sessionId)
      .run();
  }

  async function updateSessionTitle(
    db: D1DatabaseLike,
    sessionId: string,
    title: string
  ): Promise<void> {
    await db
      .prepare('UPDATE agent_sessions SET title = ? WHERE id = ?')
      .bind(title, sessionId)
      .run();
  }

  async function getSessionMessageCounts(
    db: D1DatabaseLike,
    sessionId: string
  ): Promise<{ user: number; assistant: number }> {
    const result = await db
      .prepare(
        "SELECT role, COUNT(*) as count FROM agent_messages WHERE session_id = ? AND role IN ('user','assistant') GROUP BY role"
      )
      .bind(sessionId)
      .all<{ role: string; count: number }>();

    const counts = { user: 0, assistant: 0 };
    for (const row of result.results) {
      if (row.role === 'user') {
        counts.user = row.count;
      } else if (row.role === 'assistant') {
        counts.assistant = row.count;
      }
    }
    return counts;
  }

  async function listUserMessagesForTitle(
    db: D1DatabaseLike,
    sessionId: string,
    limit: number
  ): Promise<string[]> {
    const result = await db
      .prepare(
        'SELECT content FROM agent_messages WHERE session_id = ? AND role = ? ORDER BY created_at ASC LIMIT ?'
      )
      .bind(sessionId, 'user', limit)
      .all<{ content: string }>();

    return result.results.map((row) => row.content).filter(Boolean);
  }

  return {
    listAgentSessions,
    getAgentSession,
    getAgentSessionMeta,
    createAgentSession,
    deleteAgentSession,
    saveMessage,
    updateSessionPreview,
    updateSessionTitle,
    getSessionMessageCounts,
    listUserMessagesForTitle,
  };
}
