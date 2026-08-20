import { callOpenAI } from '../../infra/llm/chat-completions';
import { collapseWhitespace, truncateText } from '../../shared/text';
import type { AgentSessionMeta } from './repository';

type WorkerExecutionContext = {
  waitUntil: (promise: Promise<unknown>) => void;
};

interface SessionTitlePreparedStatementLike {
  bind: (...values: unknown[]) => SessionTitlePreparedStatementLike;
  first: <T = Record<string, unknown>>() => Promise<T | null>;
  all: <T = Record<string, unknown>>() => Promise<{ results: T[] }>;
  run: () => Promise<unknown>;
}

interface SessionTitleDatabaseLike {
  prepare: (query: string) => SessionTitlePreparedStatementLike;
}

interface SessionTitleEnvLike {
  DB: SessionTitleDatabaseLike;
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  OPENAI_TITLE_MODEL?: string;
}

export function createSessionTitleService(deps: {
  DEFAULT_MODEL: string;
  DEFAULT_SESSION_TITLE: string;
  TITLE_MAX_CN_CHARS: number;
  TITLE_MAX_EN_WORDS: number;
  TITLE_SOURCE_USER_MESSAGES: number;
  TITLE_SOURCE_MAX_CHARS: number;
  getAgentSessionMeta: (db: SessionTitleDatabaseLike, sessionId: string) => Promise<AgentSessionMeta | null>;
  getSessionMessageCounts: (
    db: SessionTitleDatabaseLike,
    sessionId: string
  ) => Promise<{ user: number; assistant: number }>;
  listUserMessagesForTitle: (db: SessionTitleDatabaseLike, sessionId: string, limit: number) => Promise<string[]>;
  updateSessionTitle: (db: SessionTitleDatabaseLike, sessionId: string, title: string) => Promise<void>;
}) {
  function isDefaultSessionTitle(title?: string): boolean {
    const normalized = collapseWhitespace(title || '').toLowerCase();
    if (!normalized) return true;

    const aliases = [
      deps.DEFAULT_SESSION_TITLE,
      'new chat',
      'new conversation',
      'new session',
      'untitled',
      'untitled chat',
      'untitled session',
      '新会话',
    ];

    return aliases.some((alias) => normalized === alias.toLowerCase());
  }

  function containsCjk(text: string): boolean {
    return /[\u4e00-\u9fff]/.test(text);
  }

  function sanitizeGeneratedTitle(raw: string): string {
    let title = collapseWhitespace(raw || '');
    if (!title) return '';

    title = title.split('\n')[0].trim();
    title = title.replace(/^(标题|title)\s*[:：]\s*/i, '');
    title = title.replace(/^["'“”‘’]+|["'“”‘’]+$/g, '');
    title = title.replace(/[。！？!?,，、；;:：]+$/g, '');

    if (containsCjk(title)) {
      title = title.slice(0, deps.TITLE_MAX_CN_CHARS);
    } else {
      const words = title.split(/\s+/).filter(Boolean);
      title = words.slice(0, deps.TITLE_MAX_EN_WORDS).join(' ');
    }

    return title.trim();
  }

  async function generateSessionTitle(
    env: SessionTitleEnvLike,
    userMessages: string[]
  ): Promise<string | null> {
    const promptLines = userMessages.map((message, index) => {
      const cleaned = truncateText(collapseWhitespace(message), deps.TITLE_SOURCE_MAX_CHARS);
      return `用户${index + 1}: ${cleaned}`;
    });

    const systemPrompt =
      '你是对话标题生成器。根据用户前 1 到 2 句对话生成简短标题。中文 6 到 12 字，英文 3 到 6 词；不要标点、不要引号、不要换行、不要表情，只返回标题。';

    try {
      const raw = await callOpenAI(env, {
        model: env.OPENAI_TITLE_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
        temperature: 0.2,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: promptLines.join('\n') },
        ],
      });
      return raw;
    } catch (error) {
      console.warn('Title generation failed:', error);
      return null;
    }
  }

  async function maybeGenerateSessionTitle(
    env: SessionTitleEnvLike,
    sessionId: string
  ): Promise<void> {
    try {
      const session = await deps.getAgentSessionMeta(env.DB, sessionId);
      if (!session || !isDefaultSessionTitle(session.title)) {
        return;
      }

      const counts = await deps.getSessionMessageCounts(env.DB, sessionId);
      if (counts.user < 1 || counts.assistant < 1) {
        return;
      }

      const userMessages = await deps.listUserMessagesForTitle(
        env.DB,
        sessionId,
        deps.TITLE_SOURCE_USER_MESSAGES
      );
      if (!userMessages.length) {
        return;
      }

      const rawTitle = await generateSessionTitle(env, userMessages);
      if (!rawTitle) {
        return;
      }

      const nextTitle = sanitizeGeneratedTitle(rawTitle);
      if (!nextTitle || isDefaultSessionTitle(nextTitle)) {
        return;
      }

      await deps.updateSessionTitle(env.DB, sessionId, nextTitle);
    } catch (error) {
      console.warn('Title generation error:', error);
    }
  }

  function scheduleSessionTitleGeneration(
    ctx: WorkerExecutionContext | undefined,
    task: Promise<void>
  ): void {
    if (ctx?.waitUntil) {
      ctx.waitUntil(task);
      return;
    }

    task.catch((error) => {
      console.warn('Title generation failed (no waitUntil):', error);
    });
  }

  return {
    sanitizeGeneratedTitle,
    maybeGenerateSessionTitle,
    scheduleSessionTitleGeneration,
  };
}
