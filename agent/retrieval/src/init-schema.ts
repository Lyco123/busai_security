import { readFileSync } from 'fs';
import { resolve } from 'path';
import { kbRepository } from './db/repository';

async function main() {
  const schemaPath = resolve(__dirname, '../sql/schema.sql');
  const sql = readFileSync(schemaPath, 'utf8');
  await kbRepository.ensureSchemaFromSql(sql);
  await kbRepository.ensureLegacySchemaCompatibility();
  // eslint-disable-next-line no-console
  console.log('schema initialized');
}

main().catch((error) => {
  // eslint-disable-next-line no-console
  console.error('failed to initialize schema', error);
  process.exit(1);
});
