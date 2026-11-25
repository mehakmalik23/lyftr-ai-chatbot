from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from typing import Optional

from .config import settings
from .database import init_db, check_db_health, get_or_update_system_prompt, get_session_messages, save_turn
from .schemas import ChatRequest, ChatResponse
from .llm_gateway import generate_chat_completion
import litellm

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Lyftr AI Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=503, content={"detail": "all providers unavailable"})

@app.get("/health")
def health_check():
    db_ok = check_db_health()
    keys_count = len(settings.llm_api_keys)
    cache_enabled = litellm.cache is not None
    if not db_ok or keys_count < 1:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "keys_configured": keys_count, "cache_enabled": cache_enabled}
        )
    return {
        "status": "ok",
        "keys_configured": keys_count,
        "cache_enabled": cache_enabled
    }

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    payload: ChatRequest,
    x_simulate_failure: Optional[str] = Header(default=None, alias="X-Simulate-Failure")
):
    system_prompt = get_or_update_system_prompt(payload.session_id, payload.system_prompt)
    history = get_session_messages(payload.session_id)

    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})
    llm_messages.append({"role": "user", "content": payload.message})

    reply, metadata = generate_chat_completion(
        messages=llm_messages,
        simulate_header=x_simulate_failure
    )

    save_turn(
        session_id=payload.session_id,
        user_message=payload.message,
        assistant_reply=reply,
        metadata=metadata
    )

    return {
        "session_id": payload.session_id,
        "reply": reply,
        "metadata": metadata
    }

@app.get("/sessions/{session_id}/messages")
def get_history_endpoint(session_id: str):
    messages = get_session_messages(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": session_id,
        "messages": messages
    }
