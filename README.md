# LLM Chatbot with Key Failover and Response Caching

## 1. Live URLs
- **Frontend URL:** `https://YOUR-FRONTEND-URL.vercel.app`
- **Backend URL:** `https://YOUR-BACKEND-URL.hf.space`
- **Health Check:** `https://YOUR-BACKEND-URL.hf.space/health`

## 2. Run locally: with Docker and without
### With Docker
1. Copy `.env.example` to `.env` and fill in `LLM_API_KEYS` with at least 2 API keys.
2. Run `make up` to start backend (`http://localhost:8000`) and frontend (`http://localhost:3000`).
3. Run `make down` to stop both containers.

### Without Docker
1. Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Frontend: `cd frontend && npm install && npm run dev`
3. Tests: `cd backend && pytest -v`

## 3. Design decisions: key fallback, caching, SQLite session storage
- **Key Fallback:** Configured via `LLM_API_KEYS` (`key_1`, `key_2`, ...). When a key returns HTTP 429, quota error, 5xx, or matches `X-Simulate-Failure`, `llm_gateway.py` catches the failure, increments `fallback_attempts`, and fails over to the next key immediately. If all keys fail, it returns HTTP `503 {"detail": "all providers unavailable"}` and does not write to SQLite.
- **Caching:** Uses LiteLLM's built-in cache (`litellm.cache = Cache(type="local")`) keyed strictly on `model + messages (system prompt + history + new user message)`. Cache hits return `resolution_source: "LLM_CACHE"`, `key_id: null`, and `fallback_attempts: 0` across sessions.
- **SQLite Session Storage:** Uses SQLite pointed at `DATABASE_URL` (`/data/app.db` on a persistent Docker volume). Schema (`messages` and `session_configs`) is auto-created on startup.

## 4. Verification: how to see failover, cache hits and per-message token usage
- **Failover:** Toggle the **Chaos Failover Hook** buttons in the UI (`Fail key_1 (429)`, `Fail key_1 (500)`, `Fail All (*=429)`) or pass the `X-Simulate-Failure` header to `POST /chat`.
- **Cache Hits:** Send a message in a new session (`LIVE_INFERENCE`), then click **Test Cross-Session Cache Hit** in the UI to send the identical first message in a new session and observe `LLM_CACHE` with lower latency.
- **Per-Message Token Usage:** Shown inside every assistant reply under `data-testid="meta-input-tokens"` and `data-testid="meta-output-tokens"`.

## 5. Setup Used: your editor and AI tools
- **Editor & Environment:** Google Colab, VS Code, Docker
- **AI Tools:** Gemini for boilerplate generation and contract verification.

## 6. Bonus features (if any): what you added beyond the requirements and why
- **Interactive Chaos Failover Simulator in UI:** Lets reviewers trigger `X-Simulate-Failure` (`key_1=429`, `key_1=500`, `*=429`) directly from the chat interface.
- **One-Click Cross-Session Cache Tester:** Spawns a new session and resends the prompt to prove cross-session `LLM_CACHE` hits.
- **Live `/health` Telemetry Bar:** Displays active key pool count and cache status.