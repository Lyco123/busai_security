import { jsonrepair } from 'jsonrepair';

export function safeJsonParse(value: string): unknown | null {
  try {
    return JSON.parse(value);
  } catch {
    try {
      const repaired = jsonrepair(value);
      return JSON.parse(repaired);
    } catch {
      const start = value.indexOf('{');
      const end = value.lastIndexOf('}');
      if (start !== -1 && end !== -1 && end > start) {
        try {
          const snippet = value.slice(start, end + 1);
          const repairedSnippet = jsonrepair(snippet);
          return JSON.parse(repairedSnippet) as Record<string, unknown>;
        } catch {
          return null;
        }
      }
      return null;
    }
  }
}
