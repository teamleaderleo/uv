# UV local-source provenance research

Date: 2026-08-02  
State: `FINDING CONFIRMED; UPSTREAM CONTACT NOT AUTHORIZED`  
Internal carrier: `teamleaderleo/uv#11`  
Exact upstream base: `astral-sh/uv@79bbface771210df216b738e9bdc7df95e5a9e6b`

## Finding

The regression reported as “relative editable paths become absolute through a transitive Poetry dependency” is a broader **local-directory provenance regression**.

When a root project explicitly selects a local child directory with a relative `[tool.uv.sources]` path, and a local Poetry parent emits an equivalent path dependency in generated metadata, uv 0.10.10 and 0.12.1 serialize the child as an absolute path in both places below:

1. the child package's own `source` entry;
2. the parent's `[package.metadata].requires-dist` entry for that child.

This occurs for both:

- editable root/Poetry directory dependencies;
- non-editable root/Poetry directory dependencies.

The same matrix remains relative on uv 0.10.0.

## Exact version matrix

Workflow: `Fieldwork UV source provenance`  
Corrected run: `30752194973`  
Generated merge tested: `00ee711a4e5ac995adf70529f3fa66357f067967`

| uv | editable records absolute | non-editable records absolute | root dependency-order invariant | cold/warm invariant |
| --- | ---: | ---: | --- | --- |
| 0.10.0 | 0/4 source; 0/4 metadata | 0/4 source; 0/4 metadata | yes | yes |
| 0.10.10 | 4/4 source; 4/4 metadata | 4/4 source; 4/4 metadata | yes | yes |
| 0.12.1 | 4/4 source; 4/4 metadata | 4/4 source; 4/4 metadata | yes | yes |

Each version ran these eight observations:

- editable, parent-first, cold;
- editable, parent-first, warm;
- editable, child-first, cold;
- editable, child-first, warm;
- non-editable, parent-first, cold;
- non-editable, parent-first, warm;
- non-editable, child-first, cold;
- non-editable, child-first, warm.

The corrected probe normalizes each disposable case root before comparing outputs. The tested fixture therefore does **not** demonstrate dependency-order or cache-state nondeterminism. The earlier completion-order hypothesis remains a separate unproven risk, not part of the confirmed claim.

## Receipts

### uv 0.10.0

- job: `91508081313`
- result: success
- package source paths: `0/8` absolute
- parent metadata paths: `0/8` absolute
- artifact: `8834793365`
- artifact ZIP SHA-256: `a909d2961705d226cadbf08587b8ced337ef81557203480c885fa6f8541d2941`

Representative result:

```text
editable=../child
noneditable directory=../child
parent metadata directory=../child
```

### uv 0.10.10

- job: `91508081303`
- result: success
- package source paths: `8/8` absolute
- parent metadata paths: `8/8` absolute
- artifact: `8834792931`
- artifact ZIP SHA-256: `5dccfdfaa039aecc71c87c66ac86deb2e9d3420e6790d7b85bd66e12578f8256`

Representative result:

```text
editable=<CASE>/child ABSOLUTE
noneditable directory=<CASE>/child ABSOLUTE
parent metadata directory=<CASE>/child ABSOLUTE
```

### uv 0.12.1

- job: `91508081306`
- result: success
- package source paths: `8/8` absolute
- parent metadata paths: `8/8` absolute
- artifact: `8834793219`
- artifact ZIP SHA-256: `58cac6f794e65adc8194869cb7423139035a9671f16348217953f8a5bdb72d4b`

Representative result is identical in classification to 0.10.10.

## Source-level interpretation

PR `astral-sh/uv#18176`, merged as `eec8048a0b1c88cb69227cd9f77ce28c2fc61c88`, intentionally changed path serialization to preserve whether each `VerbatimUrl` was originally relative or absolute.

The relevant rule became:

```text
relativize only when !url.was_given_absolute()
```

That is sound when one source spelling has one provenance. It becomes lossy when multiple requirements point at the same local resource:

- explicit root configuration says `../child` and therefore carries relative user intent;
- generated build-backend metadata describes the same child as an absolute `file://` URL;
- resource deduplication has to select one operational source, but the surviving URL also carries presentation provenance;
- lock serialization then treats the generated absolute spelling as authoritative.

The broader invariant is:

> Resource identity and serialization provenance are different properties. When equivalent local resources are merged, explicit project configuration should determine portable presentation; generated metadata should not silently replace that intent.

This is not fundamentally an “editable” rule. Editability changes install behavior, but both editable and non-editable local directories cross the same provenance boundary.

## Active Astral draft and remaining gap

Issue `astral-sh/uv#20477` is already assigned into draft `astral-sh/uv-dev#304`, head `675839b0b1b1c66ee3b02139e1237094722ec2b2`.

The draft:

- preserves a selected relative directory source while serializing matching generated metadata;
- changes same-resource URL replacement for the reported editable/non-editable collision;
- adds one regression fixture for the editable Poetry case.

The implementation's lock-serialization set includes relative directory sources generally, so it may repair the non-editable result too. However, the current test and framing do not demonstrate that. A credible validation should add the non-editable sibling and require both package source and parent metadata to remain relative.

## Next research probes

These are separate from the confirmed finding and should not be claimed without execution:

1. Apply draft #304 and run this complete editable/non-editable matrix.
2. Test a local archive/path distribution, not only a directory distribution.
3. Test equivalent directory aliases through symlinks, because resource equality can use `is_same_file` while provenance repair keys exact install paths.
4. Test conflicting explicit provenance: one root source relative and another explicit declaration absolute for the same resource.
5. Compare `uv.lock` and `pylock.toml` so the provenance invariant is consistent across serializers.
6. Create delayed metadata fixtures before claiming asynchronous lookahead completion can alter the selected spelling.

## External-contact state

No Astral issue, pull request, comment, review, reaction, email, or other upstream contact was created. `teamleaderleo/uv#11` is an internal fork-only execution carrier and remains draft.
