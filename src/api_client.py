import json
import sys
from typing import Iterator
from .config import get_api_config


def _get_client():
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("Error: 'openai' package is required. Run: pip install openai")

    cfg = get_api_config()
    api_key = cfg["api_key"]
    base_url = cfg["base_url"]

    if not api_key:
        sys.exit("Error: No API key found. Set FM_API_KEY or OPENAI_API_KEY environment variable,\n"
                 "       or configure via: fm --set-api-key <key>")

    return OpenAI(base_url=base_url, api_key=api_key), cfg["model"]


def chat_completion(
    messages: list[dict],
    stream: bool = True,
    schema: dict = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    model: str = None,
) -> Iterator[str] | str:
    client, default_model = _get_client()
    model = model or default_model

    kwargs = dict(model=model, messages=messages, max_completion_tokens=max_tokens, temperature=temperature)

    if schema:
        kwargs["response_format"] = {"type": "json_schema", "json_schema": {"name": schema.get("name", "response"), "schema": schema}}

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
