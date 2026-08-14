from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sys

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import DCTERMS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chatgptgym.provider import ChatGPTCloudEnvironment, ChatGPTCloudProvider

SOSA_PROCEDURE = URIRef("http://www.w3.org/ns/sosa/Procedure")
READ = URIRef("urn:gymact:consequence:read")
DO = URIRef("urn:gymact:consequence:do")


@dataclass(frozen=True)
class FakeCapability:
    iri: str
    binding: str


def snapshot():
    return json.loads((ROOT / "environment/snapshot.json").read_text())


def test_snapshot_is_sanitized_and_bounded():
    data = snapshot()
    assert data["actuation_policy"]["live_external"] == "REFUSED:LIVE_EXTERNAL_ACTUATION"
    assert len(data["capability_catalog"]) >= 20
    ids = [row["id"] for row in data["capability_catalog"]]
    assert len(ids) == len(set(ids))
    forbidden_keys = {"token", "password", "secret", "credential", "authorization", "cookie"}

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key.lower() not in forbidden_keys
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)


def test_ontology_has_exact_admitted_provider_operations():
    graph = Graph().parse(ROOT / "ggen/gymact-bridge-pack/ontology.ttl", format="turtle")
    procedures = set(graph.subjects(RDF.type, SOSA_PROCEDURE))
    assert len(procedures) == 4
    titles = set()
    for procedure in procedures:
        title = list(graph.objects(procedure, DCTERMS.title))
        consequence = list(graph.objects(procedure, DCTERMS.type))
        assert len(title) == 1
        assert len(consequence) == 1
        assert consequence[0] in {READ, DO}
        titles.add(str(title[0]))
    assert titles == {"inspect-environment", "inspect-capability-catalog", "simulate-capability", "reset-simulation"}


def test_simulation_refuses_live_and_replays_checkpoint():
    async def run():
        env = ChatGPTCloudEnvironment(snapshot())
        simulate = FakeCapability("urn:chatgptgym:capability:simulate-capability", "simulate_capability")
        first = await env.actuate(simulate, {"capability": "github-write", "issue": 42})
        assert first == {"sequence": 1, "capability": "github-write", "consequence": "DO", "payload_keys": ["issue"], "disposition": "SIMULATED_ONLY"}
        checkpoint = await env.checkpoint()
        await env.actuate(simulate, {"capability": "gmail-read"})
        await env.restore(checkpoint)
        assert await env.checkpoint() == checkpoint
        try:
            await env.actuate(simulate, {"capability": "github-write", "live": True})
        except PermissionError as exc:
            assert str(exc) == "REFUSED:LIVE_EXTERNAL_ACTUATION"
        else:
            raise AssertionError("live actuation was not refused")

    asyncio.run(run())


def test_provider_refuses_live_materialization():
    async def run():
        provider = ChatGPTCloudProvider()
        try:
            await provider.materialize(scenario=None, config={"live": True})
        except PermissionError as exc:
            assert str(exc) == "REFUSED:LIVE_EXTERNAL_ACTUATION"
        else:
            raise AssertionError("live materialization was not refused")

    asyncio.run(run())
