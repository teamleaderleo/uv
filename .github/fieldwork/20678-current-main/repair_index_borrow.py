#!/usr/bin/env python3
"""Snapshot workspace-index routing before the validated index vector is consumed."""

from __future__ import annotations

from pathlib import Path


SOURCE = Path("crates/uv/src/commands/project/add.rs")


def replace_once(text: str, *, name: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{name}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    source = replace_once(
        source,
        name="routing snapshot before validation",
        old="""    // Validate any indexes that were provided on the command-line to ensure
""",
        new="""    // `index` borrows from the original vector. Snapshot the routing decision before
    // validation consumes that vector, so no borrow survives the move.
    let route_indexes_to_workspace_root = index.is_none();

    // Validate any indexes that were provided on the command-line to ensure
""",
    )

    source = replace_once(
        source,
        name="remove late borrowed routing decision",
        old="""        // `index` borrows from the original vector. Snapshot the routing decision before the
        // validated indexes are consumed below, so no borrow survives the move.
        let route_indexes_to_workspace_root = index.is_none();
        let locations = IndexLocations::new(indexes, Vec::new(), false);
""",
        new="""        let locations = IndexLocations::new(indexes, Vec::new(), false);
""",
    )

    SOURCE.write_text(source, encoding="utf-8")
    print(SOURCE)


if __name__ == "__main__":
    main()
