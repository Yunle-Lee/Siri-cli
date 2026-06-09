"""API client — OpenAI-compatible backend with guardrails and use-case support."""

import base64
import json
import sys
from pathlib import Path
from typing import Iterator

from .config import get_api_config

# ── guardrails ──────────────────────────────────────────────────────
GUARDRAIL_PROMPTS = {
    "default": "",
    "permissive": "You are a helpful assistant. Be more permissive in your responses.",
    "permissive-content-transformations": (
        "You are a helpful assistant. Be permissive with content transformations. "
        "You may rewrite, summarize, and transform any content provided by the user."
    ),
}

# ── use cases ───────────────────────────────────────────────────────
USE_CASES = {
    "general": "",
    "content-tagging": (
        "You are a content tagging assistant. Analyze the input and return relevant tags "
        "or categories in a structured format."
    ),
}


def _get_client():
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("Error: 'openai' package is required. Run: pip install openai")

    cfg = get_api_config()
    api_key = cfg["api_key"]
    base_url = cfg["base_url"]

    if not api_key:
        sys.exit(
            "Error: No API key found. Set FM_API_KEY or OPENAI_API_KEY environment variable,\n"
            "       or configure via: fm config --set-api-key <key>"
        )

    return OpenAI(base_url=base_url, api_key=api_key), cfg["model"]


def _build_instructions(
    instructions: str = None,
    guardrails: str = "default",
    use_case: str = "general",
) -> str | None:
    parts = []
    if guardrails and guardrails in GUARDRAIL_PROMPTS:
        g = GUARDRAIL_PROMPTS[guardrails]
        if g:
            parts.append(g)
    if use_case and use_case in USE_CASES:
        u = USE_CASES[use_case]
        if u:
            parts.append(u)
    if instructions:
        parts.append(instructions)
    return "\n\n".join(parts) if parts else None


def _encode_image(image_path: str) -> str:
    """Read image file and return base64 data URI."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    ext = path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")
    data = path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def chat_completion(
    messages: list[dict],
    stream: bool = True,
    schema: dict = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    model: str = None,
    guardrails: str = "default",
    use_case: str = "general",
    images: list[str] = None,
) -> Iterator[str] | str:
    client, default_model = _get_client()
    model = model or default_model

    # ── inject guardrails / use-case into messages ─────────────────
    enhanced_messages = list(messages)
    guardrail_prompt = _build_instructions(guardrails=guardrails, use_case=use_case)
    if guardrail_prompt:
        # prepend as system message or merge with existing
        if enhanced_messages and enhanced_messages[0]["role"] == "system":
            enhanced_messages[0]["content"] = guardrail_prompt + "\n\n" + enhanced_messages[0]["content"]
        else:
            enhanced_messages.insert(0, {"role": "system", "content": guardrail_prompt})

    # ── handle images ──────────────────────────────────────────────
    if images:
        user_content = []
        for img in images:
            try:
                data_uri = _encode_image(img)
                user_content.append({"type": "image_url", "image_url": {"url": data_uri}})
            except Exception as e:
                user_content.append({"type": "text", "text": f"[Image error: {e}]"})
        # append images to last user message
        last_user = None
        for msg in reversed(enhanced_messages):
            if msg["role"] == "user":
                last_user = msg
                break
        if last_user:
            if isinstance(last_user["content"], str):
                last_user["content"] = [{"type": "text", "text": last_user["content"]}]
            if isinstance(last_user["content"], list):
                last_user["content"].extend(user_content)

    kwargs = dict(
        model=model,
        messages=enhanced_messages,
        max_completion_tokens=max_tokens,
        temperature=temperature,
    )

    if schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema.get("name", "response"), "schema": schema},
        }

    if stream:
        response = client.chat.completions.create(**kwargs, stream=True)
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    else:
        response = client.chat.completions.create(**kwargs, stream=False)
        return response.choices[0].message.content or ""


def count_tokens(text: str, model: str = None) -> int:
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        return len(text.split())


def check_availability() -> dict:
    client, model = _get_client()
    try:
        models = client.models.list()
        return {"available": True, "model": model, "provider": str(client.base_url)}
    except Exception as e:
        return {"available": False, "error": str(e)}


def image_token_count(image_path: str) -> int:
    """Estimate tokens for an image. Rough approximation."""
    try:
        from pathlib import Path
        size = Path(image_path).stat().st_size
        # rough: ~85 tokens per 512x512 tile
        return max(85, size // 1024)
    except Exception:
        return 0
