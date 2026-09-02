# AGENTS.md

## Scope and repository boundary

This repository preserves legally obtained Kick-Flight client material and contains reproducible analysis and transformation tooling. It owns the asset pipeline, static-analysis inventories, and patched-APK generator. The private-server implementation belongs in the sibling `Kick-Flight-Private-Server` repository. Do not add backend endpoints, databases, matchmaking, or runtime server fixtures here.

Instructions apply to the entire repository. Read the nearest nested `AGENTS.md` as well if one is added later.

## Read before changing code

1. Inspect `git status` and preserve unrelated or user-authored changes.
2. Read `README.md` for the asset pipeline.
3. For APK work, read `apk_patch_pipeline/README.md` and `APK_PATCH_PIPELINE_CONTINUATION_PROMPT.md`.
4. For protocol research, read `server_revival_analysis/README.md`, `PRIVATE_SERVER_REVIVAL_PLAN.md`, and `protocol_inventory.json` before opening large generated dumps.
5. Consult the sibling server repository for the current runtime milestone; old prompts in this repository may describe phases already completed.

## Preservation and safety invariants

- Treat `base.apk` as immutable. Its accepted SHA-256 is `F79F1B48F86C4F5973C763CBC6C166BD6C42CC83D4E36ECA75D7D1CAB74AD8D1`.
- Never commit source or generated APKs, extracted copyrighted assets, signing keys, certificates, credentials, device identifiers, raw sensitive captures, tool downloads, or generated work directories.
- Never contact or proxy requests to the retired first-party infrastructure. Research must use local files and community-controlled services.
- Redact access tokens, advertising IDs, device UUIDs, cookies, API keys, and account identifiers. When evidence needs identity, retain only presence, length, and a short non-reversible hash.
- Do not select a public license for preserved third-party material without explicit user direction.
- Do not modify device proxy/DNS, uninstall packages, clear app data, root/remount a device, or replace signing identities unless the user explicitly puts that action in scope. Document a reversal for every device/network change.

## Patched-APK pipeline

The current implementation supports only Kick-Flight 2.11.0 and must remain fail-closed. Do not weaken source hashes, metadata checks, literal cardinality, bounds checks, or native instruction guards to make an unknown APK build.

Known native guards:

- ARM64 `0x31B5024`: `28118a9a` to `e8030aaa`.
- ARMv7 `0x2AC1798`: `02309f17` to `0000a0e1`.

Known metadata requirements are sanity `0xFAB11BAF`, header version 24, and exactly the three endpoint literals documented in the pipeline README. A new client version requires a separately named profile/implementation with its own verified APK hash, offsets, guards, tests, and documentation.

Generated pipeline state belongs only under ignored paths:

- `apk_patch_pipeline/.tools/`
- `apk_patch_pipeline/.work/`
- `apk_patch_pipeline/artifacts/`
- `apk_patch_pipeline/profiles/*.local.json`

Development signing keys are disposable local test identities. Never represent them as an official community release key.

## Editing and implementation conventions

- Make focused, reviewable edits. Prefer `apply_patch` for text changes.
- Keep scripts non-interactive where practical, validate exact targets before writes, and fail with actionable messages.
- Preserve deterministic inputs and emit provenance reports containing tool versions and SHA-256 hashes.
- Keep source and generated outputs separated. Converted assets are views; the preserved source bytes remain authoritative.
- Add tests for every parser, patch invariant, newly supported version, and failure guard.
- Avoid duplicating large decompiler output in documentation; cite paths and record only derived facts needed for reproduction.

## Required validation

For APK pipeline changes:

```powershell
python -m unittest discover -s .\apk_patch_pipeline -p 'test_*.py' -v
```

For asset pipeline changes, run the relevant unit tests and at least a one-item smoke extraction when dependencies and local inputs are available. Before every handoff run:

```powershell
git diff --check
git status --short
```

Changes to the APK orchestrator also require a complete local build when the pinned tools are available. Confirm the source hash remains unchanged, signature and alignment verification pass, the build report contains non-null patch details, and no generated artifact becomes trackable.

## Documentation and handoff

Lead with what was actually achieved and distinguish unit validation, signed build validation, and device runtime validation. Record exact commands, hashes, known limitations, and the next observed blocker. Do not claim a runtime milestone without device or emulator evidence.
