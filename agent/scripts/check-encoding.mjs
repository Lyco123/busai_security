#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { TextDecoder } from 'node:util';
import { fileURLToPath } from 'node:url';

const TEXT_EXTENSIONS = new Set([
  '.ts',
  '.tsx',
  '.js',
  '.mjs',
  '.cjs',
  '.json',
  '.md',
  '.sql',
  '.yml',
  '.yaml',
  '.toml',
  '.py',
]);

const decoder = new TextDecoder('utf-8', { fatal: true });

function git(args, cwd) {
  return execFileSync('git', args, {
    cwd,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
}

function listTrackedFiles(repoRoot) {
  const trackedOutput = execFileSync('git', ['ls-files', '-z'], {
    cwd: repoRoot,
    encoding: 'buffer',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const untrackedOutput = execFileSync('git', ['ls-files', '--others', '--exclude-standard', '-z'], {
    cwd: repoRoot,
    encoding: 'buffer',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return Buffer.concat([trackedOutput, untrackedOutput])
    .toString('utf8')
    .split('\0')
    .filter(Boolean)
    .filter((file, index, array) => array.indexOf(file) === index)
    .filter((file) => TEXT_EXTENSIONS.has(path.extname(file).toLowerCase()));
}

function findControlCharacter(content) {
  for (let i = 0; i < content.length; i += 1) {
    const code = content.charCodeAt(i);
    if (code === 0x09 || code === 0x0a) continue;
    if (code <= 0x1f || code === 0x7f) {
      return { code, index: i };
    }
  }
  return null;
}

function main() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const checkRoot = path.resolve(scriptDir, '..');
  const repoRoot = git(['rev-parse', '--show-toplevel'], scriptDir);
  const scope = path.relative(repoRoot, checkRoot).replace(/\\/g, '/');
  const files = listTrackedFiles(repoRoot).filter((file) => {
    if (scope === '' || scope === '.') return true;
    return file === scope || file.startsWith(`${scope}/`);
  });
  const failures = [];

  for (const relativePath of files) {
    const fullPath = path.join(repoRoot, relativePath);
    const bytes = fs.readFileSync(fullPath);

    if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
      failures.push(`${relativePath}: has UTF-8 BOM`);
      continue;
    }

    let content = '';
    try {
      content = decoder.decode(bytes);
    } catch (error) {
      failures.push(`${relativePath}: invalid UTF-8 (${error instanceof Error ? error.message : String(error)})`);
      continue;
    }

    if (content.includes('\uFFFD')) {
      failures.push(`${relativePath}: contains Unicode replacement character U+FFFD`);
    }

    if (content.includes('\r')) {
      failures.push(`${relativePath}: contains CR character; expected LF only`);
    }

    const control = findControlCharacter(content);
    if (control) {
      failures.push(`${relativePath}: contains control character 0x${control.code.toString(16).padStart(2, '0')}`);
    }
  }

  if (failures.length > 0) {
    console.error('Encoding check failed:\n');
    for (const failure of failures) {
      console.error(`- ${failure}`);
    }
    process.exit(1);
  }

  console.log(`Encoding check passed for ${files.length} tracked text files.`);
}

main();
