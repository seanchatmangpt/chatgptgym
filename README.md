# ChatGPTGym

ChatGPTGym is a bounded GymAct-compatible digital twin of the non-secret capability surface exposed by this ChatGPT cloud execution environment.

It intentionally does **not** clone credentials, connector data, private files, hidden prompts, chain-of-thought, model weights, service configuration, or ambient authority. The repository captures reproducible runtime facts and a sanitized capability catalog, then exposes them through an executable simulation provider.

## Architecture

```text
sanitized cloud observation
        |
        v
environment/snapshot.json
        |
        +--> ChatGPTCloudProvider (GymAct EnvironmentProvider)
        |       inspect -> READ
        |       simulate/reset -> DO (bounded world only)
        |
        +--> ggen/gymact-bridge-pack/ontology.ttl
                |
                +-- GymAct SHACL profile pinned at exact source SHA
                +-- ggen sync --> Rust operation catalog + MCP schema
```

The ggen pack is derived from GymAct's `consumer-bridge-pack-template`, pinned to GymAct commit `5a40c8f402aeb14699e216e17b2ef7aae9f0bc8f`. It declares only `sosa:Procedure` instances and reuses GymAct's READ/DO consequence IRIs.

## What is captured

- operating-system and CPU architecture facts
- selected installed runtime/tool versions observed in the execution capsule
- local binary availability/refusals
- high-level cloud capability categories (files, Python, container execution, web, GitHub, Gmail, Calendar, Drive, Contacts, automations, image generation, artifact generation, settings, user-context lookup)
- consequence class and authority requirement for each category
- network/transport observations relevant to reproducibility
- explicit exclusion/refusal policy

No raw environment variables or account data are captured.

## Provider

`chatgptgym.provider:ChatGPTCloudProvider` materializes an isolated in-memory twin. `simulate-capability` records only the capability name and payload key names. Payload values are deliberately not retained. `live=true` is refused with `REFUSED:LIVE_EXTERNAL_ACTUATION`.

The provider does not import or call ChatGPT's private connector implementations. It models the admitted public surface and preserves the authority boundary.

## ggen manufacture

From `ggen/gymact-bridge-pack/` with a compatible `ggen` binary:

```bash
ggen sync run
```

Expected manufactured surfaces:

- `src/chatgptgym_operation_catalog.rs`
- `src/chatgptgym_mcp_tools.rs`

The current source tree does not hand-author those generated files. If `ggen` is unavailable, generation is `BLOCKED:MISSING_GGEN`, not silently simulated.

## Validation

```bash
python -m pytest -q
```

The local tests prove the sanitized snapshot, RDF capability constraints, simulation/refusal semantics, checkpoint/restore, and deterministic state replay. Full GymAct crown standing additionally requires installation against the exact pinned GymAct subject, `ggen sync run`, and a real GymAct episode/OCEL replay.
