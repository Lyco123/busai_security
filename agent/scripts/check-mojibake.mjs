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

const SUSPICIOUS_CHARS = new Set([
  '锛',
  '銆',
  '鏄',
  '鍙',
  '閿',
  '鐨',
  '鍚',
  '璇',
  '缁',
  '娴',
  '闂',
  '鍐',
  '缂',
  '鑾',
  '锟',
]);

const LATIN_MOJIBAKE_RE = /(Ã.|Â.|â€|â€™|â€œ|â€\x9d)/;

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

function loadAllowlist(repoRoot) {
  const allowlistPath = path.join(repoRoot, 'agent/scripts/mojibake-allowlist.json');
  if (!fs.existsSync(allowlistPath)) {
    return { allowFiles: [], allowLineContains: [] };
  }
  const raw = fs.readFileSync(allowlistPath, 'utf8');
  const parsed = JSON.parse(raw);
  return {
    allowFiles: Array.isArray(parsed.allowFiles) ? parsed.allowFiles : [],
    allowLineContains: Array.isArray(parsed.allowLineContains) ? parsed.allowLineContains : [],
  };
}

function isAllowedFile(relativePath, allowFiles) {
  return allowFiles.some((prefix) => relativePath.startsWith(prefix));
}

function isAllowedLine(line, allowLineContains) {
  return allowLineContains.some((snippet) => line.includes(snippet));
}

function suspiciousCount(line) {
  let count = 0;
  for (const char of line) {
    if (SUSPICIOUS_CHARS.has(char)) {
      count += 1;
    }
  }
  return count;
}

function main() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const checkRoot = path.resolve(scriptDir, '..');
  const repoRoot = git(['rev-parse', '--show-toplevel'], scriptDir);
  const decoder = new TextDecoder('utf-8', { fatal: true });
  const scope = path.relative(repoRoot, checkRoot).replace(/\\/g, '/');
  const files = listTrackedFiles(repoRoot).filter((file) => {
    if (scope === '' || scope === '.') return true;
    return file === scope || file.startsWith(`${scope}/`);
  });
  const { allowFiles, allowLineContains } = loadAllowlist(repoRoot);
  const findings = [];

  for (const relativePath of files) {
    if (isAllowedFile(relativePath, allowFiles)) continue;

    const fullPath = path.join(repoRoot, relativePath);
    let content = '';
    try {
      content = decoder.decode(fs.readFileSync(fullPath));
    } catch {
      continue;
    }

    const lines = content.split('\n');
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      if (isAllowedLine(line, allowLineContains)) continue;
      if (line.trim().length === 0) continue;

      const count = suspiciousCount(line);
      const hasSuspiciousLine = count >= 6 || line.includes('锟');
      if (hasSuspiciousLine || LATIN_MOJIBAKE_RE.test(line)) {
        findings.push({
          file: relativePath,
          line: i + 1,
          preview: line.trim().slice(0, 120),
        });
      }
    }
  }

  if (findings.length > 0) {
    console.error('Mojibake check failed:\n');
    for (const item of findings.slice(0, 200)) {
      console.error(`- ${item.file}:${item.line} ${item.preview}`);
    }
    if (findings.length > 200) {
      console.error(`...and ${findings.length - 200} more findings`);
    }
    process.exit(1);
  }

  console.log(`Mojibake check passed for ${files.length} tracked text files.`);
}

main();
