from __future__ import annotations

import asyncio
import base64
import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx

from app.config.defaults import get_llm_config


def _encode_image_to_data_url(image_path: str) -> str:
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"image not found: {image_path}")
    mime, _ = mimetypes.guess_type(str(p))
    if not mime:
        ext = p.suffix.lower().lstrip(".")
        mime = f"image/{ext}" if ext else "image/png"
    with p.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


class LLMClient:
    def __init__(self, provider_cfg: dict[str, Any]):
        if not isinstance(provider_cfg, dict):
            raise TypeError("provider_cfg must be a dict")
        self.base_url: str = str(provider_cfg.get("base_url", "")).rstrip("/")
        self.api_key: str = str(provider_cfg.get("api_key", "") or "")
        self.model: str = str(provider_cfg.get("model", "") or "")
        self.vision_model: str = str(provider_cfg.get("vision_model", "") or "")
        try:
            self.temperature: float = float(provider_cfg.get("temperature", 0.2))
        except (TypeError, ValueError):
            self.temperature = 0.2
        try:
            self.timeout: float = float(provider_cfg.get("timeout", 60))
        except (TypeError, ValueError):
            self.timeout = 60.0

        self._max_retries = 2
        self._backoff_base = 1.0

    def __repr__(self) -> str:
        masked = "<none>"
        if self.api_key:
            masked = self.api_key[:4] + "***" if len(self.api_key) > 4 else "***"
        return (
            f"LLMClient(base_url={self.base_url!r}, model={self.model!r}, "
            f"vision_model={self.vision_model!r}, api_key={masked}, "
            f"temperature={self.temperature}, timeout={self.timeout})"
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _build_payload(
        self,
        messages: list[dict],
        model: str,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": bool(stream),
        }

    @staticmethod
    def _extract_text(raw: dict[str, Any]) -> str:
        try:
            choices = raw.get("choices") or []
            if not choices:
                return ""
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text" and isinstance(item.get("text"), str):
                            parts.append(item["text"])
                        elif isinstance(item.get("text"), str):
                            parts.append(item["text"])
                return "".join(parts)
            return ""
        except Exception:
            return ""

    def _request_sync(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            start = time.perf_counter()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(
                        self._chat_url(),
                        headers=self._headers(),
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                latency_ms = int((time.perf_counter() - start) * 1000)
                return data, latency_ms
            except Exception as e:
                last_err = e
                if attempt >= self._max_retries:
                    break
                time.sleep(self._backoff_base * (2 ** attempt))
        raise last_err if last_err else RuntimeError("unknown error")

    async def _request_async(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            start = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        self._chat_url(),
                        headers=self._headers(),
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                latency_ms = int((time.perf_counter() - start) * 1000)
                return data, latency_ms
            except Exception as e:
                last_err = e
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._backoff_base * (2 ** attempt))
        raise last_err if last_err else RuntimeError("unknown error")

    def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        model = model_override or self.model
        if not model:
            raise ValueError("model is empty; please configure provider.model")
        payload = self._build_payload(messages, model, stream)
        raw, latency_ms = self._request_sync(payload)
        return {
            "text": self._extract_text(raw),
            "raw": raw,
            "latency_ms": latency_ms,
        }

    async def achat(
        self,
        messages: list[dict],
        stream: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        model = model_override or self.model
        if not model:
            raise ValueError("model is empty; please configure provider.model")
        payload = self._build_payload(messages, model, stream)
        raw, latency_ms = await self._request_async(payload)
        return {
            "text": self._extract_text(raw),
            "raw": raw,
            "latency_ms": latency_ms,
        }

    def vision(
        self,
        messages_with_image: list[dict],
        image_paths: list[str],
        model_override: str | None = None,
    ) -> dict[str, Any]:
        model = model_override or self.vision_model or self.model
        if not model:
            raise ValueError("vision_model/model is empty; please configure provider")

        image_parts = [
            {"type": "image_url", "image_url": {"url": _encode_image_to_data_url(p)}}
            for p in (image_paths or [])
        ]

        messages = [dict(m) for m in messages_with_image]
        if image_parts:
            target_idx: int | None = None
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    target_idx = i
                    break
            if target_idx is None:
                messages.append({"role": "user", "content": []})
                target_idx = len(messages) - 1

            msg = dict(messages[target_idx])
            content = msg.get("content")
            if isinstance(content, str):
                new_content: list[dict] = []
                if content:
                    new_content.append({"type": "text", "text": content})
                new_content.extend(image_parts)
            elif isinstance(content, list):
                new_content = list(content) + image_parts
            else:
                new_content = list(image_parts)
            msg["content"] = new_content
            messages[target_idx] = msg

        payload = self._build_payload(messages, model, False)
        raw, latency_ms = self._request_sync(payload)
        return {
            "text": self._extract_text(raw),
            "raw": raw,
            "latency_ms": latency_ms,
        }

    def test_connection(self) -> tuple[bool, str, int]:
        start = time.perf_counter()
        try:
            result = self.chat(
                [{"role": "user", "content": "ping"}],
                stream=False,
            )
            latency_ms = int(result.get("latency_ms") or (time.perf_counter() - start) * 1000)
            text = (result.get("text") or "").strip()
            msg = f"ok: {text[:80]}" if text else "ok"
            return True, msg, latency_ms
        except httpx.HTTPStatusError as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            body = ""
            try:
                body = e.response.text[:200]
            except Exception:
                pass
            return False, f"HTTP {e.response.status_code}: {body}", latency_ms
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return False, f"{type(e).__name__}: {e}", latency_ms


def build_default_client() -> LLMClient:
    cfg = get_llm_config() or {}
    providers = cfg.get("providers") or {}
    active = cfg.get("active_provider")
    if not active or active not in providers:
        if providers:
            active = next(iter(providers.keys()))
        else:
            return LLMClient({})
    provider_cfg = providers.get(active) or {}
    if not isinstance(provider_cfg, dict):
        provider_cfg = {}
    return LLMClient(provider_cfg)
