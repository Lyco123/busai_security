import { createReadStream } from 'node:fs';
import { copyFile, mkdir, readFile, rename, rm, stat, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { config } from '../config';

function safeName(value: string): string {
  return value.replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, ' ').trim() || 'file';
}

function resolveSafe(root: string, key: string): string {
  const absoluteRoot = path.resolve(root);
  const absolutePath = path.resolve(absoluteRoot, key);
  if (!absolutePath.startsWith(absoluteRoot)) {
    throw new Error('Unsafe path key');
  }
  return absolutePath;
}

async function ensureParent(filePath: string): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true });
}

async function moveFile(fromPath: string, toPath: string): Promise<void> {
  await ensureParent(toPath);
  try {
    await rename(fromPath, toPath);
    return;
  } catch (error) {
    // Cross-device move fallback.
    const message = error instanceof Error ? error.message : String(error);
    if (!/cross-device|EXDEV/i.test(message)) {
      throw error;
    }
  }
  await copyFile(fromPath, toPath);
  await unlink(fromPath);
}

export interface SavePreviewFileInput {
  preview_id: string;
  file_name: string;
  content: Buffer;
}

export async function ensureStorageRoots(): Promise<void> {
  await mkdir(config.rawFileRoot, { recursive: true });
  await mkdir(config.rawPreviewRoot, { recursive: true });
}

export async function savePreviewFile(input: SavePreviewFileInput): Promise<string> {
  const fileName = safeName(input.file_name);
  const tempFileKey = `${input.preview_id}/${Date.now()}_${fileName}`;
  const fullPath = resolveSafe(config.rawPreviewRoot, tempFileKey);
  await ensureParent(fullPath);
  await writeFile(fullPath, input.content);
  return tempFileKey;
}

export async function commitPreviewFile(tempFileKey: string, finalFileKey: string): Promise<void> {
  const previewPath = resolveSafe(config.rawPreviewRoot, tempFileKey);
  const finalPath = resolveSafe(config.rawFileRoot, finalFileKey);
  await moveFile(previewPath, finalPath);
  try {
    await rm(path.dirname(previewPath), { recursive: true, force: true });
  } catch {
    // Ignore non-critical cleanup errors.
  }
}

export async function removePreviewFile(tempFileKey: string): Promise<void> {
  const previewPath = resolveSafe(config.rawPreviewRoot, tempFileKey);
  await rm(previewPath, { force: true });
}

export async function getStoredFileStats(fileStorageKey: string): Promise<{ size: number }> {
  const filePath = resolveSafe(config.rawFileRoot, fileStorageKey);
  const info = await stat(filePath);
  return { size: info.size };
}

export async function readStoredFile(fileStorageKey: string): Promise<Buffer> {
  const filePath = resolveSafe(config.rawFileRoot, fileStorageKey);
  return readFile(filePath);
}

export function createStoredFileReadStream(fileStorageKey: string) {
  const filePath = resolveSafe(config.rawFileRoot, fileStorageKey);
  return createReadStream(filePath);
}
