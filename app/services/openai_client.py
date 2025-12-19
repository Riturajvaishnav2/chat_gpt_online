from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from openai import AsyncOpenAI, OpenAIError
from openai import APITimeoutError


def _usage_to_dict(usage: Any) -> Optional[Dict[str, Any]]:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    out: Dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if hasattr(usage, key):
            out[key] = getattr(usage, key)
    return out or None


_CLIENT: Optional[AsyncOpenAI] = None
_DEFAULT_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))


def get_openai_client() -> AsyncOpenAI:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set it in the environment or add it to a .env file."
        )
    _CLIENT = AsyncOpenAI(api_key=api_key, timeout=_DEFAULT_TIMEOUT)
    return _CLIENT


async def generate_json_object(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    retries: int = 1,
    timeout: Optional[float] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    client = get_openai_client()
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                timeout=timeout or _DEFAULT_TIMEOUT,
            )
            content = (response.choices[0].message.content or "").strip()
            usage = _usage_to_dict(getattr(response, "usage", None))
            return content, usage
        except APITimeoutError as exc:
            last_error = exc
            if attempt < retries:
                continue
            raise HTTPException(status_code=504, detail="OpenAI request timed out.") from exc
        except OpenAIError as exc:
            last_error = exc
            if attempt < retries:
                continue
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {exc}") from exc
        except Exception as exc:  # network errors bubbled by httpx/httpcore
            last_error = exc
            if attempt < retries:
                continue
            raise HTTPException(status_code=502, detail=f"OpenAI call failed: {exc}") from exc

    # Should never reach here
    raise HTTPException(status_code=502, detail=f"OpenAI call failed: {last_error}")
