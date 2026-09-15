"""Model-provider abstractions for the local AI workstation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from reverend.config import ollama_host

from .policy import InferencePolicy


class ProviderError(RuntimeError):
    """Raised when a local inference provider fails."""


@dataclass(frozen=True)
class ModelInfo:
    name: str
    digest: str | None
    size_bytes: int | None
    modified_at: str | None
    details: dict[str, Any]


@dataclass(frozen=True)
class LoadedModelInfo:
    """Provider-observed residency facts for a currently loaded model."""

    name: str
    size_bytes: int | None
    size_vram_bytes: int | None
    context_length: int | None
    expires_at: str | None
    details: dict[str, Any] = field(default_factory=dict)


class ModelProvider(ABC):
    """Abstract interface used by the development engine."""

    @abstractmethod
    def health(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        model: str,
        prompt: str,
        *,
        context: int | None = None,
        predict: int | None = None,
        temperature: float = 0.0,
        think: bool | None = None,
        keep_alive: str | int = "10m",
        response_format: str | dict[str, Any] | None = None,
        timeout: int = 1800,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def loaded_models(self) -> list[str]:
        raise NotImplementedError

    def loaded_model_info(self) -> list[LoadedModelInfo]:
        """Return detailed residency when the provider exposes it.

        The default preserves compatibility with providers that only expose
        model names; unknown resource fields remain explicit rather than
        being estimated.
        """

        return [
            LoadedModelInfo(
                name=name,
                size_bytes=None,
                size_vram_bytes=None,
                context_length=None,
                expires_at=None,
            )
            for name in self.loaded_models()
        ]

    @abstractmethod
    def unload(self, model: str) -> None:
        raise NotImplementedError


class OllamaProvider(ModelProvider):
    """Local Ollama provider with hard endpoint validation."""

    def __init__(
        self,
        endpoint: str | None = None,
        *,
        policy: InferencePolicy | None = None,
    ) -> None:
        self.policy = policy or InferencePolicy()

        configured = endpoint or ollama_host()

        self.endpoint = (
            self.policy.validate_inference_endpoint(
                configured
            )
        )

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        data = (
            None
            if payload is None
            else json.dumps(payload).encode("utf-8")
        )

        request = urllib.request.Request(
            self.endpoint.rstrip("/") + path,
            data=data,
            headers={
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:
                return json.load(response)

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ProviderError(
                f"Ollama request failed: {path}: {exc}"
            ) from exc

    def health(self) -> bool:
        try:
            self._request(
                "/api/tags",
                timeout=5,
            )
            return True
        except ProviderError:
            return False

    def list_models(self) -> list[ModelInfo]:
        response = self._request(
            "/api/tags",
            timeout=30,
        )

        result: list[ModelInfo] = []

        for item in response.get("models", []):
            result.append(
                ModelInfo(
                    name=item.get(
                        "name",
                        item.get("model", ""),
                    ),
                    digest=item.get("digest"),
                    size_bytes=item.get("size"),
                    modified_at=item.get(
                        "modified_at"
                    ),
                    details=dict(
                        item.get("details") or {}
                    ),
                )
            )

        return result

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        context: int | None = None,
        predict: int | None = None,
        temperature: float = 0.0,
        think: bool | None = None,
        keep_alive: str | int = "10m",
        response_format: str | dict[str, Any] | None = None,
        timeout: int = 1800,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": temperature,
        }

        if context is not None:
            options["num_ctx"] = context

        if predict is not None:
            options["num_predict"] = predict

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": options,
        }

        if think is not None:
            payload["think"] = think

        if response_format is not None:
            if not (
                response_format == "json"
                or isinstance(response_format, dict)
            ):
                raise ValueError("response_format must be 'json', a JSON schema object, or None")
            payload["format"] = response_format

        return self._request(
            "/api/generate",
            payload,
            timeout=timeout,
        )

    def loaded_model_info(self) -> list[LoadedModelInfo]:
        response = self._request(
            "/api/ps",
            timeout=30,
        )

        result: list[LoadedModelInfo] = []

        for item in response.get("models", []):
            name = item.get(
                "name",
                item.get("model"),
            )

            if not name:
                continue

            result.append(
                LoadedModelInfo(
                    name=name,
                    size_bytes=item.get("size"),
                    size_vram_bytes=item.get(
                        "size_vram"
                    ),
                    context_length=item.get(
                        "context_length"
                    ),
                    expires_at=item.get(
                        "expires_at"
                    ),
                    details=dict(
                        item.get("details") or {}
                    ),
                )
            )

        return result

    def loaded_models(self) -> list[str]:
        return [
            item.name
            for item in self.loaded_model_info()
        ]

    def unload(self, model: str) -> None:
        self._request(
            "/api/generate",
            {
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": 0,
            },
            timeout=120,
        )

    def embed(self, model: str, texts: list[str], *, timeout: int = 600) -> dict:
        return self._request('/api/embed', {'model': model, 'input': texts}, timeout=timeout)

    def stream(self, model: str, prompt: str, *, cancel=None, context: int = 8192,
               predict: int = 2048, think: bool = False, keep_alive='10m',
               temperature: float = 0.2, timeout: int = 600):
        """Stream final response data; cancellation closes this HTTP request."""
        import http.client
        import socket
        import threading
        from urllib.parse import urlsplit
        address = urlsplit(self.policy.validate_inference_endpoint(self.endpoint))
        connection_type = http.client.HTTPSConnection if address.scheme == 'https' else http.client.HTTPConnection
        connection = connection_type(address.hostname, address.port, timeout=timeout)
        finished = threading.Event()
        active_socket = None
        def interrupt():
            while not finished.wait(0.1):
                if cancel is not None and cancel.is_set():
                    try:
                        if active_socket:
                            active_socket.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    return
        watcher = threading.Thread(target=interrupt, daemon=True)
        try:
            if cancel is not None and cancel.is_set():
                return
            connection.connect()
            active_socket = connection.sock
            watcher.start()
            payload = {'model':model,'prompt':prompt,'stream':True,'think':think,
                       'keep_alive':keep_alive,'options':{'num_ctx':context,'num_predict':predict,
                                                         'temperature':temperature}}
            connection.request('POST', address.path.rstrip('/') + '/api/generate',
                               json.dumps(payload), {'Content-Type':'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise ProviderError(f'Local generation returned HTTP {response.status}')
            total = 0
            while cancel is None or not cancel.is_set():
                line = response.readline(1024 * 1024 + 1)
                if not line:
                    raise ProviderError("Local stream ended before completion")
                total += len(line)
                if len(line) > 1024 * 1024 or total > 8 * 1024 * 1024:
                    raise ProviderError('Local generation exceeded response limit')
                chunk = json.loads(line)
                if chunk.get('error'):
                    raise ProviderError('Local model reported a generation error')
                yield chunk
                if chunk.get('done'):
                    return
        except (OSError, ValueError, http.client.HTTPException) as exc:
            if cancel is None or not cancel.is_set():
                raise ProviderError('Local streaming request failed') from exc
        finally:
            finished.set()
            connection.close()
