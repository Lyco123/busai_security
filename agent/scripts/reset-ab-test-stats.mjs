import { execSync } from 'node:child_process';

function hasFlag(flag) {
  return process.argv.includes(flag);
}

function readArg(name, fallback = '') {
  const index = process.argv.indexOf(name);
  if (index === -1) return fallback;
  return process.argv[index + 1] ?? fallback;
}

function quoteSql(value) {
  return value.replace(/'/g, "''");
}

function runWrangler(database, sql, remote) {
  const normalizedSql = sql.replace(/\s+/g, ' ').trim();
  const escapedSql = normalizedSql.replace(/"/g, '\\"');
  const command = ['npx', 'wrangler', 'd1', 'execute', database];
  if (remote) command.push('--remote');
  command.push('--command', `"${escapedSql}"`);
  return execSync(command.join(' '), {
    cwd: process.cwd(),
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

const experiment = readArg('--experiment');
const database = readArg('--database', 'busdemo');
const includeLegacy = hasFlag('--include-legacy');
const remote = !hasFlag('--local');
const dryRun = hasFlag('--dry-run');

if (!experiment && !includeLegacy) {
  console.error('Usage: node ./scripts/reset-ab-test-stats.mjs [--experiment <id>] [--include-legacy] [--database <name>] [--local] [--dry-run]');
  process.exit(1);
}

const conditions = [];
if (includeLegacy) {
  conditions.push("json_extract(metadata, '$.ab_test.experiment') IS NULL");
}
if (experiment) {
  conditions.push(`json_extract(metadata, '$.ab_test.experiment') = '${quoteSql(experiment)}'`);
}

const filter = conditions.join(' OR ');
const baseWhere = [
  "role = 'assistant'",
  'metadata IS NOT NULL',
  'json_valid(metadata)',
  "json_type(metadata, '$.ab_test') IS NOT NULL",
  `(${filter})`,
].join(' AND ');

const previewSql = `
SELECT
  COALESCE(json_extract(metadata, '$.ab_test.experiment'), '[null]') AS experiment,
  COUNT(*) AS count
FROM agent_messages
WHERE ${baseWhere}
GROUP BY 1
ORDER BY count DESC;
`.trim();

const updateSql = `
UPDATE agent_messages
SET metadata = json_remove(metadata, '$.ab_test', '$.routing')
WHERE ${baseWhere};
`.trim();

const verifySql = `
SELECT COUNT(*) AS count
FROM agent_messages
WHERE ${baseWhere};
`.trim();

console.log(`Previewing A/B stats records in ${database}${remote ? ' (remote)' : ' (local)'}...`);
console.log(runWrangler(database, previewSql, remote));

if (dryRun) {
  console.log('Dry run only. No data was changed.');
  process.exit(0);
}

console.log('Clearing matched A/B stats metadata...');
console.log(runWrangler(database, updateSql, remote));
console.log('Verifying remaining matched rows...');
console.log(runWrangler(database, verifySql, remote));
