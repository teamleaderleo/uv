# Current-main audit — uv extracted-wheel cache recovery

## In simple words

uv's current main branch still treats the existence of an extracted wheel directory as proof that the wheel is reusable. Public users have reported power-loss cases that left zero-byte extracted files, and the retained Fieldwork probe demonstrates that uv will reuse both zero-byte metadata and corrupted package code from the same cache archive.

A practical first repair should target the demonstrated truncation/missing-member class without adding a full byte scan to every warm-cache install. During trusted extraction, uv already knows each member path, uncompressed size, and verified CRC32. Persist an independent member manifest with the archive pointer, validate the complete path-and-size set before exposing the archive, and use the existing immutable fresh-archive plus atomic pointer replacement path for recovery. Full CRC verification remains a stronger optional or follow-up control for same-size corruption.

## Identity and scope

- Public target: `astral-sh/uv`
- Exact current public head inspected: `79bbface771210df216b738e9bdc7df95e5a9e6b`
- Prior target-executed Fieldwork source: `1da26a68629be6ae5fd7f924a7d49ff54763a7df`
- Owned evidence branch: `fieldwork/wheel-cache-crash-consistency`
- Owned evidence PR: `teamleaderleo/uv#1`
- Fieldwork owner: `teamleaderleo/fieldwork#176`
- Public report: `astral-sh/uv#16841`
- Prior public proposal: `astral-sh/uv#19562`, closed
- Retrieval date: `2026-08-03`
- Claim scope: target source plus local target-executed corruption model
- Public upstream interaction: none

## Why this target is worth continuing

- uv describes itself as stable and widely used in production.
- The public repository had approximately 87.5k stars and 3.3k forks at retrieval.
- The public issue contains independent reports tied to forced power loss and cache entries containing zero-byte extracted files.
- Clearing the cache repairs the user-visible failure, directly implicating stale extracted-cache reuse.
- Fieldwork already has a deterministic target-native reproducer and an owned fork.

These signals support continued work. They do not establish incident frequency or the number of affected installations.

## Current-source findings

### 1. Cache validity is still directory presence

**Observed source** — `crates/uv-distribution/src/archive.rs` defines `Archive::exists()` as:

```rust
self.version == ARCHIVE_VERSION && cache.archive(&self.id).exists()
```

The `Archive` payload contains archive ID, compressed-wheel hashes, wheel filename, archive version, and optional compressed size. It contains no member inventory or extracted-content receipt.

**Finding** — Current main retains the original trust boundary. An existing `archive-v0/<id>` directory is accepted without checking its members.

### 2. Pointer readers expose the archive immediately

**Observed source** — `CachedWheel::from_http_pointer()` and `CachedWheel::from_local_pointer()` read the `.http` or `.rev` pointer, call `Archive::exists()`, and expose `archive-v0/<id>` directly as the cached wheel path.

**Finding** — A readable pointer plus an existing directory is the complete reuse gate. Missing, zero-byte, truncated, or altered members are not detected there.

### 3. Publication already uses immutable archive generations

**Observed source** — `Cache::persist()`:

1. creates a random archive ID;
2. renames the completed temporary extraction into `archive-v0/<id>`;
3. creates or replaces the wheel-entry link;
4. returns the new ID.

For local/path wheels, the `.rev` pointer is written after `Cache::persist()`. For HTTP wheels, the response callback persists the archive and returns an `Archive`; the cached client then serializes that result and atomically writes the `.http` cache entry.

**Finding** — The usable pointer is published after the fresh archive exists. Recovery can retain the current append-new-generation model: build a replacement first, then atomically publish the pointer. Deleting the current archive before replacement is unnecessary.

### 4. Pointer paths already have a healing branch

**Observed source** — Streaming and download paths filter cached `Archive` values through `Archive::exists()`. If the check fails, they refresh or redownload rather than returning the stale archive.

**Finding** — Expanding the validity check from directory presence to manifest validation can reuse the existing refresh path for HTTP and local pointer families. A first prototype does not need a new delete-then-rebuild protocol.

### 5. Trusted extraction already computes useful manifest data

**Observed source** — `crates/uv-extract/src/stream.rs` validates every non-directory member's uncompressed size and CRC32 against ZIP records. It currently returns only `Vec<(PathBuf, u64)>`, discarding the verified CRC32 after extraction.

**Finding** — uv can produce a trusted member manifest without rereading files at publication time. The narrow manifest fields are:

- normalized relative path;
- uncompressed size;
- optionally the already verified CRC32;
- optional mode/type information where installation semantics depend on it.

### 6. Atomic rename is not durable publication

**Observed source** — Stream extraction writes each member through `tokio::io::BufWriter` and does not call `sync_all()` or `sync_data()`. `Cache::persist()` renames the directory and publishes a link. `uv_fs::write_atomic()` writes a temporary file and renames it without an explicit file or parent-directory sync.

**Finding** — Current code provides atomic visibility during ordinary execution. It does not provide an explicit power-loss durability receipt for extracted member data, archive-directory publication, link publication, or pointer publication.

**Limit** — Fieldwork has not executed a real power-cut/filesystem-ordering test. The retained probe mutates a completed archive and establishes unsafe reuse, not the exact kernel crash sequence.

## Separate the two failure classes

### A. Reported power-loss truncation and missing members

Public reports and the retained zero-byte test fit this class. A complete member inventory plus expected file sizes can detect it using directory enumeration and metadata calls, without reading every file body.

### B. Same-size content alteration

A path-and-size manifest cannot detect this class. Full CRC or cryptographic digest verification requires reading file contents and can turn every warm-cache reuse into work proportional to total wheel bytes.

The existing Fieldwork package-code test proves that metadata-only validation is insufficient. A new same-size corruption control should decide whether full verification belongs in the default path, an explicit cache-verification command, or a follow-up recovery mode.

## Selected first candidate

### Pointer-bound member and size manifest

Extend the independently serialized archive pointer with a backward-compatible optional manifest:

```text
manifest schema version
archive ID
archive format version
wheel filename
compressed-wheel digest set
ordered members:
  normalized path
  uncompressed size
  optional verified CRC32
  optional file mode/type
```

The manifest must be generated from trusted ZIP processing, not reconstructed from the mutable extracted directory.

At pointer-derived reuse:

1. read and decode the pointer plus manifest;
2. verify archive version and directory existence;
3. enumerate the extracted tree without following unexpected symlinks;
4. compare the complete normalized member set and file types;
5. compare each member's size;
6. return a typed valid, corrupt, legacy-unverified, or I/O result;
7. on corruption and available authority, create a new archive ID and atomically replace the pointer;
8. re-read the winning pointer after a concurrent replacement;
9. leave old or losing immutable generations for existing cache cleanup.

### Why this is the first candidate

- catches the reported zero-byte state;
- catches missing and truncated package members, not only metadata;
- uses data already computed during extraction;
- avoids reading every member body on every reuse;
- composes with current immutable archive publication;
- permits backward-compatible treatment of old pointers;
- leaves a clear extension point for CRC verification.

## Concurrency and authority judgment

### HTTP and local pointer families

The `.http` or `.rev` pointer names the archive ID consumed by `CachedWheel`. These readers need one pointer generation, not agreement with a separately read mutable archive link. Concurrent healers can safely create distinct immutable archive IDs; atomic pointer replacement chooses a winner, and readers should re-read after replacement.

A cross-platform per-wheel lock is not required for the first pointer-family prototype if:

- no current archive is deleted before a replacement exists;
- the pointer is the sole reader authority for that path;
- losers accept the winning pointer;
- orphan cleanup is safe and bounded.

### Built-wheel/link-only families

`ResolvedWheel::from_built_source()` resolves the wheel-entry link directly and does not consume an `Archive` pointer. This family needs separate validation and generation analysis. It should not be silently claimed by the pointer-family prototype.

## Rejected first moves

### Check only that `METADATA` is non-empty

The closed public PR tried this. It misses corrupted package code, missing non-metadata members, and many partial archives.

### Validate against extracted `RECORD`

The archive can corrupt or truncate its own `RECORD`. Authority must be persisted independently from the mutable extracted tree.

### Hash every member on every reuse immediately

This detects same-size corruption but imposes full archive reads on warm-cache paths. Measure it as a stronger alternative after the size/member prototype.

### Delete corrupt state before rebuilding

Deletion creates a missing window and complicates concurrent recovery. Fresh immutable generation plus atomic pointer replacement fits current publication behavior.

### Add broad cross-platform locks first

Locks may be necessary for link-only families or a later unified protocol. Pointer paths can first test lock-free immutable replacement with exact race controls.

## Required current-head experiment

Run the existing target-native corruption reproducer at `79bbface771210df216b738e9bdc7df95e5a9e6b`, then add:

1. zero-byte all-members archive;
2. zero-byte `METADATA` only;
3. truncated package module with intact metadata;
4. missing package member;
5. unexpected extra member;
6. same-size content alteration;
7. valid archive control;
8. legacy pointer without manifest;
9. corrupt/missing manifest;
10. two concurrent healers with one winning pointer generation;
11. offline HTTP cache with corrupt archive;
12. local-path wheel with original source still available.

Measure separately:

- path-and-size validation time;
- full CRC validation time;
- cold extraction time;
- warm install time for small, medium, and large wheels.

## Decision gate

Proceed to implementation only if current-head execution confirms the defect and the member/size validation overhead is small enough for the normal reuse path.

Then choose among:

- default member/size validation plus optional full CRC;
- default member/size validation plus full CRC only after suspicious metadata/I/O symptoms;
- durable-publication work plus a separate explicit `uv cache verify` path;
- stop if the performance cost or format migration is disproportionate.

## Policy and upstream boundary

uv's contribution guide asks contributors to check with maintainers before implementing issues that are not labeled for community contribution and requires compliance with Astral's AI policy. Fieldwork may continue read-only research, owned-fork experiments, and target-native execution. Any public comment, issue update, or pull request requires separate user authorization.

## Current disposition

`RETAIN — EXECUTE CURRENT HEAD`

Strongest supported finding: current uv main still reuses pointer-derived extracted wheel archives based only on directory presence, despite an open public issue and target-executed evidence that corrupt archives can be installed repeatedly.

Next action: rebase the reproducer onto `79bbface771210df216b738e9bdc7df95e5a9e6b`, execute the expanded corruption matrix, and prototype pointer-bound member/size validation before considering full-content verification.
