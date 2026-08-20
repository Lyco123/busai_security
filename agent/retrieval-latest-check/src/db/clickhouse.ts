import { createClient, type ClickHouseClient, type CommandResult } from '@clickhouse/client';
import { config } from '../config';

const ISO_UTC_DATETIME_RE = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(\.\d{1,3})?Z$/;

function normalizeClickHouseValue(value: unknown): unknown {
  if (typeof value === 'string') {
    const match = value.match(ISO_UTC_DATETIME_RE);
    if (match) {
      const [, date, time, millis = '.000'] = match;
      return `${date} ${time}${millis}`;
    }
  }
  return value;
}

function normalizeInsertRows<T extends object>(rows: T[]): T[] {
  return rows.map((row) => {
    const entries = Object.entries(row).map(([key, value]) => [key, normalizeClickHouseValue(value)]);
    return Object.fromEntries(entries) as T;
  });
}

export class ClickHouseGateway {
  private readonly client: ClickHouseClient;

  constructor() {
    this.client = createClient({
      url: config.ckDsn,
      request_timeout: config.requestTimeoutMs,
      max_open_connections: 10,
    });
  }

  async selectRows<T>(query: string, params?: Record<string, unknown>): Promise<T[]> {
    const result = await this.client.query({
      query,
      query_params: params,
      format: 'JSONEachRow',
    });
    return result.json<T>();
  }

  async selectOne<T>(query: string, params?: Record<string, unknown>): Promise<T | null> {
    const rows = await this.selectRows<T>(query, params);
    return rows[0] ?? null;
  }

  async command(query: string, params?: Record<string, unknown>): Promise<CommandResult> {
    return this.client.command({
      query,
      query_params: params,
    });
  }

  async insert<T extends object>(table: string, rows: T[]): Promise<void> {
    if (!rows.length) return;
    await this.client.insert({
      table,
      values: normalizeInsertRows(rows),
      format: 'JSONEachRow',
    });
  }
}

export const clickhouseGateway = new ClickHouseGateway();
