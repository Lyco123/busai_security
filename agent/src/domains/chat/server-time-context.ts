const DEFAULT_SERVER_TIME_ZONE = 'Asia/Shanghai';

function formatServerDateTime(date = new Date(), timeZone = DEFAULT_SERVER_TIME_ZONE): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);

  const byType = new Map(parts.map((part) => [part.type, part.value]));
  const year = byType.get('year') ?? '';
  const month = byType.get('month') ?? '';
  const day = byType.get('day') ?? '';
  const hour = byType.get('hour') ?? '';
  const minute = byType.get('minute') ?? '';
  const second = byType.get('second') ?? '';
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

export function buildServerTimeSystemPrompt(date = new Date()): string {
  const currentDateTime = formatServerDateTime(date);
  const currentDate = currentDateTime.slice(0, 10);
  return [
    'SERVER TIME CONTEXT:',
    `- Current server time: ${currentDateTime}.`,
    `- Time zone: ${DEFAULT_SERVER_TIME_ZONE}.`,
    `- Current server date: ${currentDate}.`,
    '- Resolve relative dates such as today, yesterday, this year, this month, last month, latest, and current against this server date unless the user provides a different explicit date.',
    '- If the user does not specify a year, do not assume 2025. Use the server date for relative-date interpretation, or leave optional date/partition arguments empty when the tool should query the latest available business data.',
    '- If returned business data has its own date or partition, report that actual data date rather than replacing it with the server date.',
  ].join('\n');
}
