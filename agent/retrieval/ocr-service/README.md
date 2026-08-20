# OCR Service

FastAPI service for OCR parsing of scanned PDFs and images. It is used by the RAG retrieval service when PDF preview parsing cannot extract a text layer.

## Endpoints

- `GET /health`
- `POST /ocr/parse`

Example:

```bash
curl -X POST http://127.0.0.1:8000/ocr/parse \
  -F "file=@./test.png" \
  -F "language=ch" \
  -F "mode=standard"
```

## Docker

```bash
cp .env.example .env
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

The compose file binds OCR to `127.0.0.1:8000` on the host. The RAG container reaches it through `http://host.docker.internal:8000`.
