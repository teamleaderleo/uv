#!/usr/bin/env python3
"""Apply the missing extracted-wheel archive candidate to an exact uv checkout."""

from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text()
    actual = text.count(old)
    if actual != count:
        raise SystemExit(
            f"pointer candidate fragment mismatch in {path}: expected {count}, found {actual}"
        )
    path.write_text(text.replace(old, new))


replace(
    root / "crates/uv-distribution/src/archive.rs",
    "    pub(crate) fn exists(&self, cache: &Cache) -> bool {",
    "    pub fn exists(&self, cache: &Cache) -> bool {",
)

replace(
    root / "crates/uv-distribution/src/distribution_database.rs",
    """        let archive = pointer
            .filter(|pointer| pointer.is_up_to_date(modified))
            .map(PathArchivePointer::into_archive)
            .filter(|archive| archive.has_digests(hashes));
""",
    """        let archive = pointer
            .filter(|pointer| pointer.is_up_to_date(modified))
            .map(PathArchivePointer::into_archive)
            .filter(|archive| archive.has_digests(hashes))
            .filter(|archive| archive.exists(self.build_context.cache()));
""",
)

replace(
    root / "crates/uv-installer/src/plan.rs",
    "if archive.satisfies(hasher.get(dist.as_ref())) {",
    "if archive.exists(cache) && archive.satisfies(hasher.get(dist.as_ref())) {",
    count=3,
)
