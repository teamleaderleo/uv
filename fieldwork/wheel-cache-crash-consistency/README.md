# Wheel cache crash-consistency boundary

Source revision: `1da26a68629be6ae5fd7f924a7d49ff54763a7df`

Public report: [cached wheel archive can survive with zero-byte files](https://redirect.github.com/astral-sh/uv/issues/16841)

Prior closed proposal: [validate cached wheel archives against corruption](https://redirect.github.com/astral-sh/uv/pull/19562)

Upstream contact performed: `false`

## Current source order

The current path has two distinct claims:

1. extraction writes each wheel member into a temporary directory through an async buffered writer;
2. `Cache::persist()` renames that directory into `archive-v0`, then publishes a link from the wheel cache entry to the archive ID.

The rename gives namespace atomicity during ordinary execution. It does not, by itself, prove that every extracted file and the renamed directory entry are durable across sudden power loss.

`Archive::exists()` currently checks only:

- archive format version equality; and
- whether the archive directory exists.

It therefore treats a present directory as a complete reusable archive without validating the extracted contents.

## Confirmed failure class from the report

After a power interruption, an archive directory remained present while extracted files, including `METADATA`, were zero bytes. Resolution metadata remained usable, so package resolution succeeded and installation later failed while reading the extracted archive.

Deleting the cache or bypassing it forced a clean extraction and recovered.

The important defect boundary is broader than an empty `METADATA` file: a cache entry can be published and trusted without proof that its complete extracted contents are usable.

## Why the previous proposal was incomplete

Checking only that one `METADATA` file is non-empty catches the reported symptom but does not establish archive integrity.

It can miss:

- truncated package code with intact metadata;
- a valid-looking but incomplete metadata file;
- missing data files;
- size or digest disagreement with `RECORD`;
- a completion marker that reached disk while earlier data did not.

It also places package-format parsing inside a cheap existence check without defining the complete cache validity contract.

## Candidate protocol families

### A. Durable publish

Before the archive becomes reachable:

1. finish extraction;
2. flush and synchronize extracted files that must survive a crash;
3. synchronize the staging directory;
4. rename staging into the archive bucket;
5. synchronize the archive parent directory;
6. publish the wheel-cache link;
7. synchronize the link parent when durability is required.

Strength: prevents the reported power-loss state when implemented correctly.

Cost: potentially expensive synchronization across every extracted file and platform-specific directory semantics.

### B. Completion marker without data synchronization

Write a marker after extraction and require it on reuse.

Strength: handles process termination before normal completion.

Limit: a marker alone does not prove that prior file data survived sudden power loss. The marker can become durable independently of file contents.

### C. Validate against wheel `RECORD` on reuse

Treat the extracted archive as untrusted until every required member agrees with the wheel's recorded size and digest, then invalidate and re-extract on disagreement.

Strength: detects missing, truncated, and altered extracted files.

Cost: reads and hashes the archive on cache reuse unless validation receipts are cached safely.

### D. Heal on first semantic read failure

When metadata parsing or installation encounters a corrupt cached archive, invalidate it and retry extraction once.

Strength: cheap common path and useful defense in depth.

Limit: catches only corruption encountered by that operation. Intact metadata with damaged package code may pass installation and fail later.

## Recommended experiment order

1. reproduce trust of a deliberately corrupted extracted archive using an isolated cache;
2. identify every call site that relies on `Archive::exists()` as proof of usability;
3. fault the boundary before rename, after rename, before link publication, and after link publication;
4. compare full `RECORD` validation cost with synchronization cost on representative wheels;
5. keep automatic invalidate-and-refetch as recovery even if durable publish is added;
6. define Windows, Linux, and macOS semantics separately where directory synchronization differs.

## Added artifacts

- `repro_corrupt_archive.py` builds a tiny wheel, installs it with an isolated cache, truncates the cached extracted metadata, and retries the same install.
- `crash_model.py` compares directory-existence trust, marker-only trust, durable publish, and full content validation over bounded crash states.
- `candidate.patch` records a reviewable direction, not an implementation claim.

## Draft upstream summary

The extracted wheel cache currently publishes a renamed directory and later treats directory existence as proof that the archive is reusable. A sudden power loss can preserve the directory entry while losing file contents, after which later installs trust the damaged archive.

A complete repair needs an explicit cache validity contract. A non-empty metadata check catches one manifestation but does not protect package files or prove durability. The first patch should pair a focused corruption regression with either a durable publication protocol or complete archive validation, plus invalidate-and-refetch recovery.

## Validation still required

- execute the isolated-cache reproducer on current uv;
- confirm the exact cache path and reuse path on Linux, macOS, and Windows;
- measure full `RECORD` validation overhead;
- test interruption and hard-power-loss approximations separately;
- inspect whether the original wheel bytes remain available for local healing;
- review the final design with a human-written upstream explanation.
