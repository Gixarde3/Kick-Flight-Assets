# Kick-Flight private-server revival plan

## Outcome and recommended strategy

Revive the game in vertical slices. First make the original client boot into a seeded local account and enter training; then restore progression and social functions; only then implement OpenMatch and Photon-compatible multiplayer. The realtime layer is the highest-risk component and should not block the first playable preservation milestone.

Recommended implementation stack:

- ASP.NET Core on .NET 8 for the HTTP API and the exact OpenMatch gRPC surface already represented by the recovered C# types.
- SQLite for the first single-node milestone, migrated to PostgreSQL before community accounts are opened.
- Redis only when matchmaking, presence, and multi-instance deployment require it.
- Caddy or nginx for TLS termination and static asset delivery.
- Docker Compose for reproducible development and community hosting.
- A separate realtime compatibility process for Photon protocol work; do not mix it into the account API.

## What static analysis established

### Client and patching surface

The supplied APK is version `2.11.0` (`versionCode 55`), package `jp.grenge.kickflight`, built with Unity `2018.4.11f1`. It uses IL2CPP metadata version `24.1`, with ARM64 and ARMv7 native binaries. Game logic therefore cannot be recovered as normal method-bearing C# DLLs. Il2CppDumper recovered types, fields, method signatures, native addresses, literals, and dummy assemblies; native disassembly is still required for method bodies that matter.

The Android network-security configuration is revival-friendly:

- cleartext traffic is allowed;
- user-installed certificate authorities are trusted;
- `localhost` and `192.168.0.96` are explicitly present;
- no Java-layer certificate pinning was found in the decompiled application code.

Start with DNS/hosts redirection and a local trusted CA. Patch the APK only when a value is constructed internally or cannot be redirected externally. This keeps client changes small and auditable.

### Service topology

1. Control plane: `NetworkManager` compiles in `kickflight-api.grenge.jp`, HTTP/HTTPS selection, 30-second timeout, three retries, and a large set of `Colorful.Networking` request/response DTOs. Evidence points to JSON request/response bodies; confirm the exact envelope dynamically before implementing contracts.
2. Assets: Octo uses `colorful-api-octo-sb.grenge.jp`, `kickflight-resource-api.grenge.jp`, an `X-OCTO-KEY` header, protobuf catalog data, and UnityFS/CRI payloads. The existing preservation pipeline already recovered the payload side of this system.
3. Matchmaking: the client contains the OpenMatch `openmatch.Frontend` gRPC contract with unary `CreateTicket`, `DeleteTicket`, `GetTicket`, and server-streaming `GetAssignments`.
4. Realtime: assignment results lead into Photon PUN/LoadBalancing. The client uses rooms, player and room custom properties, events, buffered RPCs, master-client authority, region selection, and reconnect/rejoin flows.
5. Ancillary SDKs: Firebase, Repro, Adjust, Facebook, Helpshift, billing, ARCore, and platform stores are present. None should be required for the preservation server. Stub or disable them unless a proven startup dependency exists.

The OpenMatch protobuf is sufficiently explicit to recreate immediately:

- `Ticket`: `id`, `google.protobuf.Struct properties`, `Assignment`.
- `Assignment`: `connection`, `Struct properties`, `google.rpc.Status error`.
- `GetAssignmentsRequest`: `ticket_id`.
- `GetAssignmentsResponse`: `assignment`.

### Recovered request metadata

The client contains these first-party header names:

- `x-app-access-token`
- `x-app-adid` and `x-app-adjust-adid`
- `x-app-application-version`
- `x-app-asset-platform`, `x-app-asset-revision`, `x-app-asset-version`
- `x-app-country-code`, `x-app-language`, `x-app-datetime`
- `x-app-device-name`, `x-app-os-version`, `x-app-platform`, `x-app-user-agent`
- `x-app-master-hash`
- `x-app-response-cache-id`
- `x-app-status-code`, `x-app-user-id`
- `X-OCTO-KEY`

Treat header values and validation rules as unknown until captured from the client. For the private server, accept legacy headers for compatibility but issue new opaque session tokens and never depend on retired Firebase credentials or original signing secrets.

## Dependency-ordered implementation

### Phase 0 — Preservation baseline

Deliverables:

- Keep `base.apk` immutable and identify it by SHA-256.
- Keep the reconstructed UnityFS bundles and original Octo bytes immutable.
- Record tool versions and hashes, already present in this analysis directory.
- Put every future client patch in a reproducible script; never distribute an unexplained modified binary.
- Establish a short project policy: interoperability/preservation only, no original service access, no monetization, and no redistribution of assets to people who do not have a lawful copy.

Exit gate: a clean checkout can reproduce the static inventory and all hashes.

### Phase 1 — Instrumented client and redirect harness

Tasks:

1. Use an Android emulator or spare physical device with the original APK.
2. Redirect the three first-party domains to a LAN host through local DNS. Because user CAs and cleartext are allowed, begin with a trusted local CA and TLS names matching the original hosts.
3. Run a capture proxy in front of a catch-all server. Log method, path, headers, request bytes, response expectation, ordering, and retry behavior. Redact device IDs and tokens.
4. Return controlled JSON/HTTP errors to discover which endpoints are hard blockers and which are optional.
5. If TLS or integrity logic still blocks execution, trace the native `NetworkManager.InitializeAsync`, `LoadData`, and `SetEnvironment` methods using their recovered RVAs. Patch only the domain/SSL decision or use a runtime hook during research.
6. Disable analytics, push, billing, and social initialization only if they block startup.

Exit gate: the client reaches the title flow while all first-party traffic is captured locally, with no request escaping to retired production services.

### Phase 2 — Contract reconstruction and golden fixtures

Tasks:

1. Convert the recovered `Colorful.Networking` types into DTO schemas. Begin with fields from `dump.cs`; verify field casing and null/default behavior against captured payloads.
2. Reconstruct the common response envelope, error codes, `x-app-status-code`, cache behavior, and token refresh behavior.
3. Map route literal to request/response type and caller. The machine-generated route candidates are in `protocol_inventory.json`.
4. Reconstruct native code only for ambiguous transformations: auth hash creation, URL construction, serialization, compression, and master-hash checks.
5. Store one redacted request and response fixture for every implemented endpoint. Make fixtures executable contract tests.

Highest-priority startup contracts:

1. `boot/*` or the observed boot route.
2. `auth/prepare`, `auth/create`, `auth/index`.
3. agreement read/data-usage endpoints if gated by locale/account state.
4. `download/master` and master/hash checks.
5. `startup/*` and `home/*` observed by the capture.
6. user creation/change/display-ID endpoints needed by tutorial onboarding.

Exit gate: schemas and fixtures reproduce the complete request sequence from launch through the first home-screen attempt.

### Phase 3 — Minimal control-plane server

Implement these modules, even if several initially return fixed data:

- Compatibility middleware: legacy headers, request IDs, application version, locale, and standardized errors.
- Identity: generated community account ID, opaque access token, device association, and optional invite code. Do not clone production authentication.
- Version/maintenance: allow version 2.11.0 and expose a community maintenance message.
- Boot/startup/home: return a deterministic seeded player state.
- Master-data revision: one pinned revision and hash.
- Tutorial/profile: nickname, birthday/region flags, tutorial step, initial kicker/discs/items.
- Admin bootstrap: a local CLI or protected admin endpoint to reset/test accounts. Never expose recovered debug/admin routes publicly.

Start with SQLite and a single process. Add PostgreSQL only after the schema stops changing quickly.

Exit gate: a fresh install creates a new account, completes required agreements, downloads/checks master data, and renders the home screen after an app restart.

### Phase 4 — Asset/catalog compatibility

Tasks:

1. Correlate the recovered Octo `Database`, `Data`, `Url`, and `UrlList` structures with the current `octo_sorted` and reconstructed UnityFS inventory.
2. Recreate the minimum catalog response expected by the APK: app ID, revision, tags, bundle IDs, sizes, hashes, dependencies, and URL format.
3. Serve byte-identical bundles and CRI files over ranged HTTP with stable ETags/content lengths.
4. Prefer matching the original Octo catalog format. If encryption/key derivation makes this disproportionate, patch the client at the small Octo URL/catalog boundary and document the patch.
5. Build a completeness test that starts from all bundles referenced by the startup, home, tutorial, and training scenes and verifies every dependency is present.

Exit gate: a clean client cache can download all required preserved content from the private host and load home/tutorial assets without falling back to the original domains.

### Phase 5 — First playable slice: tutorial and training

Tasks:

- Seed a known-compatible player loadout and master revision.
- Implement tutorial start/end, tutorial gacha/kicker/disc steps, training start/result, and any mission updates triggered by them.
- Run training without OpenMatch or Photon where the client supports its offline/training path.
- Persist results idempotently so retries do not duplicate rewards.
- Compare before/after DTO snapshots to find every mutated player-state field.

Exit gate: a new player can launch, complete or skip onboarding, play training, receive a result, return home, close the app, and resume correctly.

This is the first community-demo milestone.

### Phase 6 — Progression and social surface

Implement by feature group, driven by actual UI reachability:

- loadouts: kicker, disc, gear, costume, buildup and selection;
- economy: inventory, presents, missions, free/non-monetized shop operations;
- profile/search/follow/follower/real-friend;
- ranking with a community-only season model;
- announcements and web views served from local static pages.

Disable purchases and paid currency initially. If the community later wants donations, keep them completely outside the legacy game economy.

Exit gate: all non-PvP screens used by the community work without unimplemented-request popups and survive concurrency/idempotency tests.

### Phase 7 — OpenMatch-compatible matchmaking

Implement the recovered gRPC frontend exactly:

1. `CreateTicket` stores a ticket and normalized properties.
2. A simple deterministic matcher groups compatible tickets by mode, region, and party/team constraints.
3. `GetAssignments` streams an assignment once a group is ready.
4. `GetTicket` supports polling/debugging and `DeleteTicket` is idempotent.
5. The assignment `connection` and properties must carry precisely what `NormalMatchingController` expects before it invokes Photon connection.

Do not deploy the full upstream Open Match platform first. The client-facing contract is small, and a lightweight compatible implementation is easier to debug. Replace it later only if scale demands it.

Exit gate: two clients receive the same deterministic assignment and proceed to the realtime connection step; cancellation, timeout, and reconnect paths are covered.

### Phase 8 — Photon realtime compatibility

Treat this as a separate reverse-engineering project.

Tasks:

1. Inventory only the Photon operations the game calls: NameServer/region discovery, authentication, master/game-server transition, create/join/rejoin/leave room, custom properties, events, RPCs, interest groups, actor lifecycle, and cached events.
2. Extract every game-specific room/player property name and type from `dump.cs`. Important recovered families include room state/timing, battle info/rules, master player, score, team, disconnect state, and AI flags.
3. Extract every `[PunRPC]` method, Photon event code, serialization callback, prefab ID, and authority assumption.
4. Decide after a spike between:
   - a legally available Photon Server compatible runtime, if its protocol/version can be made to match this PUN client; or
   - a purpose-built compatibility gateway implementing only the observed LoadBalancing/PUN subset.
5. Keep battle authority as close to the original model as possible for the first release. Add server validation later; changing authority while also recreating the wire protocol multiplies risk.
6. Test with two, four, and eight local clients, packet loss, host/master departure, rejoin, timeout, and late join where supported.

Exit gate: a complete community match can form, load, start, synchronize, finish, submit results once, and return all participants home. A reconnect must not duplicate rewards.

### Phase 9 — Community operations

- New account/password or invite authentication, independent of all retired credentials.
- Rate limiting, audit logs, moderation roles, bans, and display-name policy.
- Daily encrypted database backup plus periodic restore drills.
- Health checks for API, asset store, matcher, and realtime process.
- Metrics without device fingerprinting; crash reports must be opt-in and community-hosted.
- Signed, reproducible client patch releases and an updater manifest controlled by the community.
- Clear version pinning: server build, APK hash, asset revision, database migration, and protocol revision.

Exit gate: another trusted maintainer can restore the service from documentation and backups without the original developer machine.

## Suggested repository layout for implementation

```text
server/
  docker-compose.yml
  src/
    KickFlight.Api/          # HTTP compatibility API
    KickFlight.Contracts/    # recovered DTOs and fixtures
    KickFlight.Matchmaker/   # OpenMatch-compatible gRPC frontend
    KickFlight.Realtime/     # isolated Photon compatibility work
    KickFlight.AssetServer/  # Octo catalog and asset URLs
  tests/
    ContractTests/
    ClientJourneyTests/
    RealtimeTests/
  fixtures/
    redacted/
  migrations/
client-patch/
  scripts/
  patches/
  manifests/
ops/
  caddy/
  backups/
  monitoring/
```

## Validation matrix

Every phase should be tested on both a warm and empty client cache.

| Journey | One client | Two clients | Restart | Retry/timeout | Empty cache |
| --- | --- | --- | --- | --- | --- |
| Boot/auth/home | required | n/a | required | required | required |
| Tutorial/training | required | n/a | required | required | required |
| Loadout/progression | required | concurrent updates | required | required | required |
| Matchmaking | required | required | cancellation | required | n/a |
| Realtime battle | local solo/AI | required | reconnect | packet loss | required |
| Battle result | required | required | required | idempotent | n/a |

## Main risks and mitigations

1. Native method bodies are absent from dummy DLLs. Use recovered RVAs with Ghidra/IDA only for the small set of URL, hash, serialization, and matching methods that dynamic capture cannot resolve.
2. No live production server means no known-good response corpus. Use controlled-error probing, client state transitions, DTO field names, and binary branch tracing to synthesize minimal valid responses.
3. Master data may contain essential balance/config beyond exported assets. Locate cached catalog/master databases in the extracted device snapshot; if absent, infer the minimum from bundle `MonoBehaviour`/`TextAsset` content and recovered DTOs.
4. Photon compatibility may dominate schedule. Preserve a valuable offline/training build first, keep realtime isolated, and publish multiplayer only after deterministic multi-client tests pass.
5. Legacy SDK shutdowns can create unrelated failures. Remove or stub Firebase analytics/push, billing, social login, Helpshift, Repro, Adjust, and AR functionality from the community client as blockers are proven.
6. APK signing changes can invalidate store/social integrations. The community build must use its own signing key and its own identity system; do not attempt to impersonate the historical publisher signature.

## Immediate next work package

The next implementation sprint should stop at the Phase 2 exit gate:

1. Create local DNS/TLS names for the three first-party hosts.
2. Build a catch-all ASP.NET Core logger returning configurable fixtures.
3. Run a fresh APK through title startup and record the ordered requests.
4. Recreate DTOs only for the observed startup sequence.
5. Add golden contract tests and return the first structurally valid boot/auth response.

That sprint will replace the remaining protocol assumptions with observed contracts and yield a reliable estimate for the first playable training milestone.
