# OCR + RAG 部署手册

本文说明如何在 RAG 同一台服务器上部署 OCR 服务，并让 RAG 在知识库上传扫描版 PDF 时自动调用 OCR。

## 1. 目录位置

OCR 服务已经放到 RAG 服务目录下：

```text
agent/retrieval/
  ocr-service/
    main.py
    api/ocr.py
    services/ocr_engine.py
    Dockerfile
    docker-compose.yml
```

RAG 调用位置：

```text
agent/retrieval/src/services/document-parser.ts
agent/retrieval/src/services/ocr-client.ts
```

处理逻辑：

1. TXT/MD/DOCX 仍按原逻辑解析。
2. PDF 先用本地 `pdf-parse` 抽文本层。
3. 如果 PDF 没有可抽取文本层，且 `OCR_ENABLED=true`，RAG 调用 OCR 服务。
4. 如果 OCR 未启用，扫描版 PDF 仍返回 `PDF_OCR_REQUIRED`。

## 2. 配置 RAG

在服务器的 `agent/retrieval/.env` 中新增或修改：

```env
OCR_ENABLED=true
OCR_BASE_URL=http://host.docker.internal:8000
OCR_TIMEOUT_MS=120000
OCR_LANGUAGE=ch
```

说明：

- `OCR_ENABLED=false` 时保持旧行为，不调用 OCR。
- `OCR_BASE_URL` 使用 `host.docker.internal`，因为 OCR 单独部署在宿主机 127.0.0.1:8000。
- RAG 的 `docker-compose.yml` 和 `docker-compose.server.yml` 都需要有 `extra_hosts` 映射；当前已处理。
- OCR 只由 `kb-api` 在 preview 上传时调用，`kb-worker` 不需要访问 OCR。

## 3. 部署 OCR

在服务器上进入 OCR 目录：

```bash
cd /opt/retrieval/ocr-service
cp .env.example .env
```

CPU 服务器建议先用保守配置：

```env
OCR_MAX_CONCURRENCY=1
OCR_TIMEOUT_SECONDS=120
OCR_WORKER_BOOT_TIMEOUT_SECONDS=180
USE_GPU=false
```

启动 OCR：

```bash
docker compose up -d --build
```

检查健康状态：

```bash
curl http://127.0.0.1:8000/health
```

预期：

```json
{"status":"ok"}
```

直接测试 OCR：

```bash
curl -X POST http://127.0.0.1:8000/ocr/parse \
  -F "file=@./test.png" \
  -F "language=ch" \
  -F "mode=standard"
```

成功响应会包含：

```json
{
  "success": true,
  "full_text": "...",
  "pages": []
}
```

## 4. 更新并重启 RAG

如果服务器使用外部 ClickHouse：

```bash
cd /opt/retrieval
docker compose -f docker-compose.server.yml up -d --build --force-recreate
docker exec -it kb-api node dist/init-schema.js
```

如果服务器使用 RAG 自带的完整 compose：

```bash
cd /opt/retrieval
docker compose up -d --build --force-recreate
docker exec -it kb-api node dist/init-schema.js
```

验证 RAG 容器能访问 OCR：

```bash
docker exec -it kb-api node -e "fetch('http://host.docker.internal:8000/health').then(r=>r.text()).then(console.log)"
```

预期：

```json
{"status":"ok"}
```

## 5. 端到端验证

上传扫描版 PDF 到 RAG preview：

```bash
curl -X POST http://127.0.0.1:8080/v1/documents/preview \
  -H "X-Tenant-Id: bus-prod" \
  -H "X-Caller-Level: company" \
  -H "X-Caller-Id: op-001" \
  -H "X-Caller-Company-Id: first-branch" \
  -F "kb_id=regulations" \
  -F "title=scanned-pdf-test" \
  -F "default_min_level=company" \
  -F "file=@./scanned.pdf"
```

预期结果：

- 返回 `preview.clauses`。
- 如果实际走了 OCR，`preview.warnings` 会包含 `PDF_OCR_APPLIED`。
- OCR 成功时不应再返回 `PDF_OCR_REQUIRED`。

## 6. 排查

RAG 仍返回 `PDF_OCR_REQUIRED`：

```bash
docker exec -it kb-api printenv | grep OCR
```

确认：

```env
OCR_ENABLED=true
OCR_BASE_URL=http://host.docker.internal:8000
```

RAG 返回 `OCR_TIMEOUT`：

- 增大 RAG 的 `OCR_TIMEOUT_MS`。
- 增大 OCR 的 `OCR_TIMEOUT_SECONDS`。
- 服务器内存紧张时降低 `OCR_MAX_CONCURRENCY=1`。

宿主机能访问 OCR，但 `kb-api` 访问不到：

```bash
docker exec -it kb-api node -e "fetch('http://host.docker.internal:8000/health').then(r=>r.text()).then(console.log)"
```

如果失败，确认 compose 中有：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

修改 compose 后要重建容器：

```bash
docker compose -f docker-compose.server.yml up -d --force-recreate
```

查看 OCR 日志：

```bash
cd /opt/retrieval/ocr-service
docker compose logs -f ocr-service
```
