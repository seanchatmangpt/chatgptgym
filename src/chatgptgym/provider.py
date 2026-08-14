"""GymAct provider for a sanitized, simulation-only ChatGPT cloud twin."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

_SNAPSHOT = Path(__file__).resolve().parents[2] / "environment" / "snapshot.json"


class ChatGPTCloudEnvironment:
    """Executable bounded twin; never calls live connectors or external systems."""

    def __init__(self, snapshot: dict[str, Any], *, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:chatgptgym:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._snapshot = deepcopy(snapshot)
        self._state: dict[str, Any] = {"sequence": 0, "events": []}
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Any, ...]:
        """Return real GymAct Capability values when GymAct is installed."""
        self._ensure_open()
        from gymact.models import Capability, Consequence

        specs = (
            ("inspect-environment", Consequence.READ, "inspect_environment"),
            ("inspect-capability-catalog", Consequence.READ, "inspect_catalog"),
            ("simulate-capability", Consequence.DO, "simulate_capability"),
            ("reset-simulation", Consequence.DO, "reset_simulation"),
        )
        return tuple(
            Capability(
                iri=f"urn:chatgptgym:capability:{name}",
                title=name,
                consequence=consequence,
                binding=binding,
            )
            for name, consequence, binding in specs
        )

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {"snapshot": deepcopy(self._snapshot), "simulation": deepcopy(self._state)}

    async def actuate(self, capability: Any, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        binding = str(capability.binding)

        if binding == "inspect_environment":
            return {"snapshot": deepcopy(self._snapshot)}
        if binding == "inspect_catalog":
            return {"capabilities": deepcopy(self._snapshot["capability_catalog"])}
        if binding == "reset_simulation":
            before = deepcopy(self._state)
            self._state = {"sequence": 0, "events": []}
            return {"before": before, "after": deepcopy(self._state), "capability": capability.iri}
        if binding != "simulate_capability":
            raise ValueError(f"REFUSED:UNSUPPORTED_BINDING:{binding}")

        if payload.get("live") is True:
            raise PermissionError("REFUSED:LIVE_EXTERNAL_ACTUATION")
        target = payload.get("capability")
        if not isinstance(target, str):
            raise TypeError("payload.capability must be a string")
        catalog = {item["id"]: item for item in self._snapshot["capability_catalog"]}
        if target not in catalog:
            raise ValueError(f"REFUSED:UNKNOWN_CAPABILITY:{target}")

        self._state["sequence"] += 1
        event = {
            "sequence": self._state["sequence"],
            "capability": target,
            "consequence": catalog[target]["consequence"],
            "payload_keys": sorted(str(k) for k in payload if k not in {"capability", "live"}),
            "disposition": "SIMULATED_ONLY",
        }
        self._state["events"].append(event)
        return deepcopy(event)

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if not isinstance(checkpoint, dict) or set(checkpoint) != {"sequence", "events"}:
            raise ValueError("REFUSED:INVALID_CHECKPOINT")
        self._state = deepcopy(checkpoint)

    async def teardown(self) -> None:
        self._closed = True


class ChatGPTCloudProvider:
    """Materializes isolated simulation-only snapshots of the admitted cloud surface."""

    name = "chatgpt-cloud"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> ChatGPTCloudEnvironment:
        del scenario
        if config.get("live") is True:
            raise PermissionError("REFUSED:LIVE_EXTERNAL_ACTUATION")
        with _SNAPSHOT.open("r", encoding="utf-8") as fh:
            snapshot = json.load(fh)
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return ChatGPTCloudEnvironment(snapshot, requires_authority=requires_authority)
