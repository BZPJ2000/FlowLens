# Environment

## Backend

Install backend dependencies from the repository root:

```powershell
python -m pip install -r backend/requirements.txt
```

Start the API:

```powershell
python backend/run_dev.py
```

Default backend URL:

```text
http://127.0.0.1:8879
```

## Frontend

Install frontend dependencies:

```powershell
cd frontend
npm install
```

Start the Vite app:

```powershell
npm run dev -- --host 127.0.0.1
```

Default frontend URL:

```text
http://127.0.0.1:5173
```

## DeepSeek

The project reads `.env` from the repository root and also supports `POLTAISHOW_ENV_FILE`.

Required values:

```text
POLTAISHOW_LLM_ENABLED=true
TEXT_AI_BASE_URL=https://api.deepseek.com
TEXT_AI_API_KEY=replace-with-your-key
TEXT_AI_MODEL=deepseek-chat
```

Compatible aliases are also accepted:

```text
DEEPSEEK_BASE_URL
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

If the model is not configured or the request fails, the chat endpoint falls back to a local static graph answer.

Do not commit `.env`; commit `.env.example` only.
