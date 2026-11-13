# Mukana Renderer

Stateless RenderCV microservice. It accepts a structured CV, cover letter and
supporting documents, then returns PDFs. It has no database and no user state,
so it can run locally behind a tunnel or on a VPS without changing the web app.

## Run locally

```powershell
$env:RENDER_SECRET = (Get-Content "$env:USERPROFILE\.mukana\render.secret" -Raw).Trim()
& "C:\Users\mmash\.conda\envs\prefect_env\python.exe" -m uvicorn renderer.app:app --host 127.0.0.1 --port 8091
```

## API

`POST /render` with header `x-render-secret`.

```json
{
  "theme": "harvard",
  "cv": { "name": "...", "sections": {} },
  "cover_letter": "Dear Hiring Manager, ...",
  "attachments": [
    { "name": "National ID.pdf", "mime": "application/pdf", "content_base64": "..." }
  ],
  "merge": true
}
```

Returns base64-encoded `cv_pdf`, `cover_letter_pdf`, `cover_letter_docx` and
`merged_pdf`, plus page counts.

## Deploy

Build and run the Docker image anywhere that can run Python and Typst:

```bash
docker build -t mukana-renderer .
docker run -p 8091:8091 -e RENDER_SECRET=... mukana-renderer
```
