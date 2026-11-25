"""LLM calls over OpenAI-compatible chat-completions APIs, with a disk cache.

Models are named `provider:model_name`, e.g. `mistral:mistral-small-latest`,
`openai:gpt-4o`, `vllm:mistralai/Mistral-7B-Instruct-v0.3`. The provider table
maps each provider to a base URL and the environment variable holding its key.
This module never reads `.env`; the caller loads it into the environment.

Only `model`, `messages`, `temperature` and `max_tokens` are sent. Provider-specific
parameters (seeds, `response_format`, ...) are deliberately not used, so a request
means the same thing on every provider; output structure is enforced by our own
parser (mas_sim.output).
"""

import asyncio
import hashlib
import itertools
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from openai import AsyncOpenAI


@dataclass(frozen=True)
class Provider:
    base_url: str | None  # fixed base URL; None = SDK default (OpenAI) or read from base_url_env
    key_env: str | None  # env var with the API key; None = local server without auth
    base_url_env: str | None = None  # env var with the base URL (local servers)


PROVIDERS: dict[str, Provider] = {
    "openai": Provider(base_url=None, key_env="OPENAI_API_KEY"),
    "mistral": Provider(base_url="https://api.mistral.ai/v1", key_env="MISTRAL_API_KEY"),
    "vllm": Provider(base_url=None, key_env=None, base_url_env="VLLM_BASE_URL"),
    "ollama": Provider(base_url=None, key_env=None, base_url_env="OLLAMA_BASE_URL"),
}


def split_model(model: str) -> tuple[str, str]:
    """'mistral:mistral-small-latest' -> ('mistral', 'mistral-small-latest')."""
    assert ":" in model, f"model must be 'provider:name', got {model!r}"
    provider, name = model.split(":", 1)
    assert provider in PROVIDERS, f"unknown provider {provider!r}; known: {sorted(PROVIDERS)}"
    assert name, f"empty model name in {model!r}"
    return provider, name


# --- message normalization -------------------------------------------------------
#
# Some chat templates (notably several Mistral instruct models served by vLLM or
# Ollama) reject two consecutive messages with the same role, and some older ones
# reject a system message. Normalization rewrites the message list so such models
# accept it. It changes the prompt, so the mode is part of the cache key and of the
# logged call record, and the logged messages are the normalized ones.

NORMALIZATIONS = ("none", "merge", "merge_fold_system")
MERGE_SEPARATOR = "\n\n"
_ROLES = ("system", "user", "assistant")


def validate_messages(messages: list[dict]) -> None:
    assert isinstance(messages, list) and messages, "messages must be a non-empty list"
    for i, m in enumerate(messages):
        assert set(m) == {"role", "content"}, f"message {i} has keys {sorted(m)}"
        assert m["role"] in _ROLES, f"message {i} has role {m['role']!r}"
        assert isinstance(m["content"], str) and m["content"].strip(), f"message {i} is empty"
        if m["role"] == "system":
            assert i == 0, f"system message at position {i}; only position 0 is allowed"


def normalize_messages(messages: list[dict], mode: str) -> list[dict]:
    """Return a new message list rewritten according to `mode`.

    none: unchanged.
    merge: consecutive messages with the same role are joined with MERGE_SEPARATOR.
    merge_fold_system: the system message is prepended to the first user message,
        then as `merge`.
    After merge modes, roles strictly alternate user/assistant (after an optional
    system message) and the first non-system message is a user message; otherwise
    AssertionError.
    """
    assert mode in NORMALIZATIONS, f"unknown normalization {mode!r}"
    validate_messages(messages)
    msgs = [dict(m) for m in messages]
    if mode == "none":
        return msgs
    if mode == "merge_fold_system" and msgs[0]["role"] == "system":
        system, rest = msgs[0], msgs[1:]
        assert rest and rest[0]["role"] == "user", "cannot fold system prompt: no user message follows it"
        rest[0] = {"role": "user", "content": system["content"] + MERGE_SEPARATOR + rest[0]["content"]}
        msgs = rest
    merged: list[dict] = []
    for m in msgs:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1] = {"role": m["role"], "content": merged[-1]["content"] + MERGE_SEPARATOR + m["content"]}
        else:
            merged.append(m)
    body = merged[1:] if merged[0]["role"] == "system" else merged
    assert body and body[0]["role"] == "user", "first non-system message must be a user message"
    for a, b in itertools.pairwise(body):
        assert a["role"] != b["role"], "roles do not alternate after merging"
    return merged


# --- backends --------------------------------------------------------------------


class Backend(Protocol):
    async def chat(
        self, provider: str, model_name: str, messages: list[dict], temperature: float, max_tokens: int
    ) -> tuple[str, str]:
        """Return (reply text, finish_reason)."""
        ...


class OpenAIBackend:
    """Real API calls via the `openai` SDK (which retries transient errors itself)."""

    def __init__(self, max_retries: int = 6, timeout_s: float = 120.0) -> None:
        self._clients: dict[str, AsyncOpenAI] = {}
        self._max_retries = max_retries
        self._timeout_s = timeout_s

    def _client(self, provider: str) -> AsyncOpenAI:
        if provider not in self._clients:
            from openai import AsyncOpenAI

            p = PROVIDERS[provider]
            if p.key_env is not None:
                assert os.environ.get(p.key_env), (
                    f"environment variable {p.key_env} is not set (needed for provider {provider!r}); "
                    "put it into the repo's .env"
                )
                api_key = os.environ[p.key_env]
            else:
                # Local servers ignore the key, but the SDK refuses an empty one.
                api_key = "unused-local"
            base_url = p.base_url
            if p.base_url_env is not None:
                assert os.environ.get(p.base_url_env), (
                    f"environment variable {p.base_url_env} is not set (needed for provider {provider!r})"
                )
                base_url = os.environ[p.base_url_env]
            self._clients[provider] = AsyncOpenAI(
                api_key=api_key, base_url=base_url, max_retries=self._max_retries, timeout=self._timeout_s
            )
        return self._clients[provider]

    async def chat(self, provider, model_name, messages, temperature, max_tokens):
        client = self._client(provider)
        # max_tokens, not max_completion_tokens: Mistral and local OpenAI-compatible
        # servers accept max_tokens; OpenAI reasoning models would need the other one.
        resp = await client.chat.completions.create(
            model=model_name, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        assert len(resp.choices) == 1, f"expected 1 choice, got {len(resp.choices)}"
        choice = resp.choices[0]
        text = choice.message.content
        if text is None:
            raise RuntimeError(f"{provider}:{model_name} returned no text (finish_reason={choice.finish_reason})")
        return text, str(choice.finish_reason)


# --- client with cache -----------------------------------------------------------


@dataclass(frozen=True)
class Completion:
    text: str
    sent_messages: list[dict]  # after normalization: exactly what the API received
    finish_reason: str
    cache_hit: bool


class LLMClient:
    """Cached, concurrency-limited access to chat models.

    Cache key: (model, normalization, normalized messages, temperature, max_tokens,
    replicate). `replicate` is part of the key so that repeated runs of the same
    condition get independent samples, while re-running the same replicate (resuming
    a sweep, re-analysis) returns the stored reply. One JSON file per entry.
    """

    def __init__(self, cache_dir: Path | None, backend: Backend | None = None, max_concurrency: int = 8) -> None:
        self.cache_dir = cache_dir
        self.backend = backend if backend is not None else OpenAIBackend()
        self._sem = asyncio.Semaphore(max_concurrency)
        self.n_api_calls = 0
        self.n_cache_hits = 0

    async def complete(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        replicate: int,
        normalization: str = "none",
    ) -> Completion:
        provider, name = split_model(model)
        assert 0.0 <= temperature <= 2.0, temperature
        assert max_tokens > 0, max_tokens
        sent = normalize_messages(messages, normalization)
        key_obj = {
            "model": model,
            "normalization": normalization,
            "messages": sent,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "replicate": replicate,
        }
        key = hashlib.sha256(json.dumps(key_obj, sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / key[:2] / f"{key}.json" if self.cache_dir is not None else None
        if path is not None and path.exists():
            entry = json.loads(path.read_text())
            assert entry["request"] == key_obj, f"cache entry {path} does not match its key"
            self.n_cache_hits += 1
            return Completion(entry["text"], sent, entry["finish_reason"], cache_hit=True)
        async with self._sem:
            text, finish_reason = await self.backend.chat(provider, name, sent, temperature, max_tokens)
        # Checked here, before the cache write, so a malformed reply is never stored and
        # replayed. Reasoning models (e.g. mistral-large-latest = Large 4, 26-11-25)
        # return a list of thinking/text chunks instead of a string; extracting and
        # logging those chunks is not supported yet.
        if not isinstance(text, str):
            raise TypeError(
                f"{model} returned {type(text).__name__} content, not str (finish_reason={finish_reason}); "
                "reasoning models that return content chunks are not supported"
            )
        self.n_api_calls += 1
        if path is not None:
            _atomic_write_json(path, {"request": key_obj, "text": text, "finish_reason": finish_reason})
        return Completion(text, sent, finish_reason, cache_hit=False)


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, suffix=".tmp") as f:
        json.dump(obj, f)
        tmp = Path(f.name)
    tmp.replace(path)
