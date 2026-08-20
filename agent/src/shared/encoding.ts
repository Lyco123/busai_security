export function normalizeTextEol(value: string): string {
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}
