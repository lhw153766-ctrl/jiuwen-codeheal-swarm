"""Dual-mode configuration for the CodeHeal Swarm engine.

The swarm supports two interchangeable reasoning back-ends:

``live``
    Real LLM-driven mode. When an API key is available (via environment
    variables or ``~/.jiuwenswarm/config/config.yaml``) the engine builds a real
    :class:`openjiuwen.core.foundation.llm.model_clients`-compatible client so
    that ``LLMComponent`` / ``WorkflowAgent`` nodes can call DeepSeek / OpenAI /
    Huawei ModelArts (and any other provider openjiuwen supports).

``replay``
    Deterministic Replay / Mock mode. When no API key is configured (CI runners,
    offline reviewers) the engine never crashes: every LLM node falls back to a
    deterministic local policy that inspects structured state produced by the
    real tools and emits a stable, reproducible decision. This lets the *entire*
    openjiuwen workflow graph (node transitions, tool execution, branch routing)
    run end-to-end with zero network access.

Configuration resolution order (highest priority last):

1. Built-in defaults.
2. ``~/.jiuwenswarm/config/config.yaml`` (JiuwenSwarm native config location).
3. ``.env`` files in the current working directory.
4. Process environment variables.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

try:  # PyYAML is an openjiuwen dependency; guard so import never hard-fails.
    import yaml
except Exception:  # pragma: no cover - yaml always present in practice
    yaml = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Provider registry                                                            #
# --------------------------------------------------------------------------- #

#: Maps the ``MODEL_PROVIDER`` short name to the openjiuwen ``ProviderType`` key.
PROVIDER_ALIASES: dict[str, str] = {
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "modelarts": "ModelArts",
    "huawei": "ModelArts",
    "maas": "ModelArts",
    "qianfan": "Qianfan",
    "siliconflow": "SiliconFlow",
    "zhipu": "Zhipu",
    "dashscope": "DashScope",
    "moonshot": "Moonshot",
    "minimax": "MiniMax",
    "anthropic": "Anthropic",
}


class EngineMode(str, Enum):
    """Which reasoning back-end the swarm should drive LLM nodes with."""

    LIVE = "live"
    REPLAY = "replay"


# --------------------------------------------------------------------------- #
# Sub-configs                                                                  #
# --------------------------------------------------------------------------- #


class ModelClientSettings(BaseModel):
    """Connection settings for the openjiuwen model client."""

    model_config = {"protected_namespaces": ()}

    provider: str = Field(default="deepseek", description="Provider short-name (see PROVIDER_ALIASES).")
    api_base: Optional[str] = Field(default=None, description="API base URL override.")
    api_key: Optional[str] = Field(default=None, description="API key; None means replay mode.")
    model_name: str = Field(default="deepseek-chat", description="Model identifier.")
    timeout: float = Field(default=60.0, description="Per-request timeout in seconds.")
    max_retries: int = Field(default=2, description="Retries before giving up on a live call.")


class HealingSettings(BaseModel):
    """Tunable knobs for the four-phase healing loop."""

    max_iterations: int = Field(default=3, ge=1, le=10, description="Max ReAct self-correction rounds.")
    pytest_timeout: int = Field(default=120, ge=5, le=900, description="Sandbox pytest wall-clock cap (s).")
    keep_sandbox: bool = Field(default=False, description="Do not delete the temp sandbox after run (debug).")


# --------------------------------------------------------------------------- #
# Root config                                                                  #
# --------------------------------------------------------------------------- #


class CodeHealConfig(BaseModel):
    """Top-level configuration object.

    Build it with :meth:`CodeHealConfig.load` which performs the full
    layered resolution described in the module docstring.
    """

    model_config = {"protected_namespaces": ()}

    mode: EngineMode = Field(default=EngineMode.REPLAY, description="Active reasoning back-end.")
    client: ModelClientSettings = Field(default_factory=ModelClientSettings)
    healing: HealingSettings = Field(default_factory=HealingSettings)
    jiuwenswarm_config_path: Optional[str] = Field(
        default=None, description="Explicit JiuwenSwarm config path (else auto-discovered)."
    )

    # ------------------------------------------------------------------ #
    # Factories                                                          #
    # ------------------------------------------------------------------ #
    @classmethod
    def load(
        cls,
        *,
        overrides: Optional[dict[str, Any]] = None,
        config_path: Optional[os.PathLike[str] | str] = None,
    ) -> "CodeHealConfig":
        """Resolve configuration from disk + environment, then apply overrides."""
        data: dict[str, Any] = {}

        # Layer 2: JiuwenSwarm native config.
        data.update(_read_jiuwenswarm_config(config_path))

        # Layer 3: .env files.
        data.update(_read_dotenv())

        # Layer 4: real process environment (highest precedence).
        data.update(_read_environ())

        # Explicit overrides win over everything.
        if overrides:
            data.update(_deep_update({}, overrides))

        cfg = cls(**_nest(data))

        # Auto-select mode: if a key materialised, we are LIVE; otherwise REPLAY.
        if cfg.client.api_key:
            cfg = cfg.model_copy(update={"mode": EngineMode.LIVE})
        elif cfg.mode == EngineMode.LIVE and not cfg.client.api_key:
            cfg = cfg.model_copy(update={"mode": EngineMode.REPLAY})
        return cfg

    @property
    def is_live(self) -> bool:
        return self.mode == EngineMode.LIVE and bool(self.client.api_key)

    @property
    def llm(self) -> ModelClientSettings:
        """Alias for self.client (backward compatibility and ergonomics)."""
        return self.client

    @property
    def provider_type(self) -> str:
        """Canonical openjiuwen ``ProviderType`` key for the configured provider."""
        key = self.client.provider.lower()
        return PROVIDER_ALIASES.get(key, self.client.provider)

    def require_live(self) -> None:
        """Raise if the engine was asked to run live without credentials."""
        if not self.is_live:
            raise RuntimeError(
                "Live LLM mode requested but no API key configured. Set API_KEY (and optionally "
                "API_BASE / MODEL_PROVIDER / MODEL_NAME) or ~/.jiuwenswarm/config/config.yaml, or "
                "run in the default deterministic replay mode."
            )


# --------------------------------------------------------------------------- #
# Layered loaders                                                              #
# --------------------------------------------------------------------------- #


def _candidate_config_paths(config_path: Optional[os.PathLike[str] | str]) -> list[Path]:
    paths: list[Path] = []
    if config_path is not None:
        paths.append(Path(config_path))
    paths.append(Path.home() / ".jiuwenswarm" / "config" / "config.yaml")
    paths.append(Path.cwd() / ".jiuwenswarm" / "config" / "config.yaml")
    paths.append(Path.cwd() / "config.yaml")
    return paths


def _read_jiuwenswarm_config(config_path: Optional[os.PathLike[str] | str]) -> dict[str, Any]:
    """Read the JiuwenSwarm-native YAML config if present."""
    if yaml is None:  # pragma: no cover
        return {}
    for path in _candidate_config_paths(config_path):
        try:
            if path.is_file():
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if isinstance(raw, dict):
                    return _flatten_jiuwenswarm(raw)
        except Exception:
            continue
    return {}


def _flatten_jiuwenswarm(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a JiuwenSwarm config.yaml onto our flat config keys."""
    out: dict[str, Any] = {}
    model = raw.get("model") or raw.get("llm") or {}
    if isinstance(model, dict):
        out["MODEL_PROVIDER"] = model.get("provider") or model.get("provider_type")
        out["MODEL_NAME"] = model.get("model_name") or model.get("name") or model.get("model")
        out["API_BASE"] = model.get("api_base") or model.get("base_url")
        out["API_KEY"] = model.get("api_key") or model.get("key")
    # Direct top-level overrides too.
    for key in ("MODEL_PROVIDER", "MODEL_NAME", "API_BASE", "API_KEY"):
        if key in raw:
            out.setdefault(key, raw[key])
    return {k: v for k, v in out.items() if v is not None}


def _read_dotenv() -> dict[str, Any]:
    """Minimal .env parser (no external dependency)."""
    out: dict[str, Any] = {}
    for candidate in (Path.cwd() / ".env", Path.home() / ".jiuwenswarm" / ".env"):
        try:
            if not candidate.is_file():
                continue
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in out:
                    out[k] = v
        except Exception:
            continue
    return out


def _read_environ() -> dict[str, Any]:
    keys = ("MODEL_PROVIDER", "MODEL_NAME", "API_BASE", "API_KEY", "CODEHEAL_MODE")
    return {k: os.environ[k] for k in keys if os.environ.get(k)}


# --------------------------------------------------------------------------- #
# dict helpers                                                                 #
# --------------------------------------------------------------------------- #


def _nest(flat: dict[str, Any]) -> dict[str, Any]:
    """Group flat env keys into nested pydantic structure."""
    client: dict[str, Any] = {}
    healing: dict[str, Any] = {}
    out: dict[str, Any] = {}
    for key, value in flat.items():
        if key in {"MODEL_PROVIDER", "MODEL_NAME", "API_BASE", "API_KEY"}:
            client[_snake(key)] = value
        elif key == "CODEHEAL_MODE":
            out["mode"] = value
        else:
            out[key] = value
    if client:
        out["client"] = client
    if healing:
        out["healing"] = healing
    return out


def _snake(key: str) -> str:
    return {
        "MODEL_PROVIDER": "provider",
        "MODEL_NAME": "model_name",
        "API_BASE": "api_base",
        "API_KEY": "api_key",
    }[key]


def _deep_update(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base
