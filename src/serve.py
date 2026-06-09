"""HTTP Chat Completions API server, OpenAI-compatible."""

import json
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
from .api_client import chat_completion
from .config import get_api_config

app = FastAPI(title="fm-clone API", version="1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models():
    cfg = get_api_config()
    return {
        "object": "list",
        "data": [
            {"id": cfg["model"], "object": "model", "created": int(time.time()), "owned_by": "fm-clone"},
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}}, status_code=400)

    messages = body.get("messages", [])
    if not messages:
        return JSONResponse({"error": {"message": "messages is required", "type": "invalid_request_error"}}, status_code=400)

    model = body.get("model", get_api_config()["model"])
    stream = body.get("stream", False)
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_completion_tokens", body.get("max_tokens", 4096))
    response_format = body.get("response_format")

    schema = None
    if response_format and response_format.get("type") == "json_schema":
        schema = response_format.get("json_schema", {}).get("schema")

    if stream:
        async def generate():
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            try:
                for chunk in chat_completion(messages, stream=True, schema=schema, temperature=temperature, max_tokens=max_tokens, model=model):
                    data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
    else:
        try:
            result = chat_completion(messages, stream=False, schema=schema, temperature=temperature, max_tokens=max_tokens, model=model)
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": result}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        except Exception as e:
            return JSONResponse({"error": {"message": str(e), "type": "api_error"}}, status_code=500)


def run_server(host: str = "127.0.0.1", port: int = 1977, socket_path: str = None):
    if socket_path:
        uvicorn.run(app, uds=socket_path)
    else:
        uvicorn.run(app, host=host, port=port)
