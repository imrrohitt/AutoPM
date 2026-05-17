"""HTTP clients for project LLM providers (LiteLLM-compatible + Ollama native)."""

import httpx

from modules.llm.models import LLMConfig


def _auth_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _normalize_base_url(base_url: str | None, default: str) -> str:
    return (base_url or default).rstrip("/")


async def test_ollama_generate(config: LLMConfig) -> tuple[bool, str]:
    base = _normalize_base_url(config.base_url, "http://localhost:11434")
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base}/api/generate",
            json={
                "model": config.model,
                "prompt": "Reply with exactly: OK",
                "stream": False,
            },
        )
        if response.status_code >= 400:
            return False, response.text[:500]
        data = response.json()
        reply = (data.get("response") or "").strip()
        return True, f"Ollama OK — model replied: {reply[:80] or '(empty)'}"


async def test_openai_compatible(
    config: LLMConfig,
    api_key: str | None,
    *,
    default_base: str,
) -> tuple[bool, str]:
    base = _normalize_base_url(config.base_url, default_base)
    url = f"{base}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            headers=_auth_headers(api_key),
            json={
                "model": config.model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 16,
                "stream": False,
            },
        )
        if response.status_code >= 400:
            return False, response.text[:500]
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return True, f"Connection OK — model replied: {str(content).strip()[:80] or '(empty)'}"


async def chat_completion(
    config: LLMConfig,
    api_key: str | None,
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> str:
    """Single-turn or multi-turn chat; returns assistant text."""
    limit = max_tokens or min(config.max_tokens, 8192)

    if config.provider == "anthropic":
        from anthropic import Anthropic

        key = api_key
        if not key:
            raise ValueError("Anthropic API key required")
        client = Anthropic(api_key=key)
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            else:
                user_messages.append(m)
        create_kwargs: dict = {
            "model": config.model,
            "max_tokens": limit,
            "messages": user_messages,
        }
        if system.strip():
            create_kwargs["system"] = system.strip()
        response = client.messages.create(**create_kwargs)
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts)

    if config.provider == "ollama":
        base = _normalize_base_url(config.base_url, "http://localhost:11434")
        ollama_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("system", "user", "assistant")
        ]
        body: dict = {
            "model": config.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"num_predict": limit},
        }
        if json_mode:
            body["format"] = "json"
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(f"{base}/api/chat", json=body)
            response.raise_for_status()
            data = response.json()
            content = (data.get("message") or {}).get("content") or ""
            if not content.strip():
                # Fallback for older Ollama builds without /api/chat
                response = await client.post(
                    f"{base}/api/generate",
                    json={
                        "model": config.model,
                        "prompt": "\n\n".join(
                            f"{m['role'].upper()}: {m['content']}" for m in ollama_messages
                        )
                        + "\n\nASSISTANT:",
                        "stream": False,
                        "options": {"num_predict": limit},
                        **({"format": "json"} if json_mode else {}),
                    },
                )
                response.raise_for_status()
                content = response.json().get("response") or ""
            text = content.strip()
            if not text:
                raise ValueError(
                    f"Ollama model '{config.model}' returned an empty response. "
                    "Try a stronger model (e.g. llama3.2, qwen2.5-coder)."
                )
            return text

    defaults = {
        "litellm": "http://localhost:4000",
        "openai": "https://api.openai.com/v1",
        "groq": "https://api.groq.com/openai/v1",
    }
    base = _normalize_base_url(config.base_url, defaults.get(config.provider, "http://localhost:4000"))
    url = f"{base}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            url,
            headers=_auth_headers(api_key),
            json={
                "model": config.model,
                "messages": messages,
                "max_tokens": limit,
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )


async def test_anthropic(api_key: str, model: str) -> tuple[bool, str]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=16,
        messages=[{"role": "user", "content": "Reply with OK"}],
    )
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text
    return True, f"Anthropic OK — {text.strip()[:80]}"
