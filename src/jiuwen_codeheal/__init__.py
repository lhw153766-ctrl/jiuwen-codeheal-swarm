"""Jiuwen-CodeHeal Swarm.

A repository-level CI fault self-healing and regression verification multi-agent
system built on top of the openJiuwen workflow engine and the JiuwenSwarm
multi-agent collaboration runtime.

The package is intentionally split into:

* :mod:`jiuwen_codeheal.config`   - dual-mode (Live LLM / Deterministic Replay) configuration.
* :mod:`jiuwen_codeheal.schemas`  - Pydantic data models for the whole state / trajectory.
* :mod:`jiuwen_codeheal.tools`    - the four real tools (log parser, AST inspector,
  sandbox verifier, skill evolver).
* :mod:`jiuwen_codeheal.workflows.heal_swarmflow` - the openJiuwen Workflow graph that
  orchestrates the four-phase Leader-Teammate healing loop.
* :mod:`jiuwen_codeheal.swarm_leader` - the Leader controller wiring the phases together.
* :mod:`jiuwen_codeheal.cli`      - the terminal front-end.
"""

from __future__ import annotations

__all__ = [
    "__version__",
    "CodeHealConfig",
    "HealingStatus",
]

__version__ = "0.1.0"


def __getattr__(name: str):  # pragma: no cover - thin lazy import shim
    if name == "CodeHealConfig":
        from jiuwen_codeheal.config import CodeHealConfig

        return CodeHealConfig
    if name == "HealingStatus":
        from jiuwen_codeheal.schemas import HealingStatus

        return HealingStatus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
