#!/usr/bin/env python3
"""
AI Chat Backend - FastAPI Proxy for xah.io API
Fixed: CORS, streaming, model routing, error handling
"""
import os
import json
import httpx
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

# Config
XAH_API_KEY = os.getenv("XAH_API_KEY", "")
XAH_API_URL = os.getenv("XAH_API_URL", "https://api.xah.io/v1/chat/completions")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
MODELS = [m.strip() for m in os.getenv("MODELS", "mistral-medium-3.5-128b").split(",")]
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", MODELS[0] if MODELS else "mistral-medium-3.5-128b")

# HTTP Client (keep-alive)
http_client: Optional[httpx.AsyncClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    )
    yield
    await http_client.aclose()

app = FastAPI(
    title="AI Chat Backend",
    description="Proxy API for xah.io with model selection",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ MODELS ============
class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str

class ChatRequest(BaseModel):
    model: str = Field(default=DEFAULT_MODEL)
    messages: List[ChatMessage]
    stream: bool = Field(default=True)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=4096, ge=1, le=32000)

class ModelInfo(BaseModel):
    id: str
    name: str
    description: str

# ============ ENDPOINTS ============
@app.get("/")
async def root():
    return {"status": "ok", "service": "ai-chat-backend", "version": "1.0.0"}

@app.get("/api/models")
async def get_models():
    """Return available models with metadata"""
    model_data = []
    for m in MODELS:
        if "mistral-medium" in m:
            desc = "Mistral Medium 3.5 - Cân bằng tốc độ và chất lượng"
        elif "mistral-small" in m:
            desc = "Mistral Small 4 - Nhanh, nhẹ, phù hợp tác vụ đơn giản"
        elif "qwen3-coder" in m:
            desc = "Qwen3 Coder 480B - Chuyên gia lập trình, code và debug"
        else:
            desc = "Model AI"
        model_data.append({"id": m, "name": m.split("-")[0].upper() + " " + "-".join(m.split("-")[1:3]), "description": desc})
    return {"models": model_data, "default": DEFAULT_MODEL}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Proxy chat to xah.io API.
    Supports both streaming and non-streaming.
    """
    if not XAH_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")

    if request.model not in MODELS:
        raise HTTPException(status_code=400, detail=f"Model {request.model} not available. Choose from: {MODELS}")

    payload = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "stream": request.stream,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens
    }

    headers = {
        "Authorization": f"Bearer {XAH_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json" if not request.stream else "text/event-stream",
        "User-Agent": "AI-Chat-Backend/1.0"
    }

    try:
        if request.stream:
            return StreamingResponse(
                stream_chat(payload, headers),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            resp = await http_client.post(XAH_API_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                detail = f"Upstream error {resp.status_code}"
                try:
                    body = resp.json()
                    detail = body.get("error", {}).get("message", detail)
                except:
                    pass
                raise HTTPException(status_code=resp.status_code, detail=detail)
            return resp.json()

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gateway timeout - upstream took too long")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot connect to AI service")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

async def stream_chat(payload: dict, headers: dict) -> AsyncGenerator[str, None]:
    """Stream SSE from xah.io to client"""
    try:
        async with http_client.stream("POST", XAH_API_URL, json=payload, headers=headers) as response:
            if response.status_code != 200:
                error_body = ""
                async for chunk in response.aiter_text():
                    error_body += chunk
                yield f"data: {json.dumps({'error': True, 'message': f'Upstream error {response.status_code}: {error_body}'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    try:
                        parsed = json.loads(data)
                        # Re-serialize to ensure valid JSON
                        yield f"data: {json.dumps(parsed)}\n\n"
                    except json.JSONDecodeError:
                        continue
    except asyncio.CancelledError:
        yield f"data: {json.dumps({'error': True, 'message': 'Request cancelled by client'})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': True, 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

@app.get("/api/health")
async def health():
    return {"status": "healthy", "models_loaded": len(MODELS)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host=HOST, port=PORT, reload=False)
