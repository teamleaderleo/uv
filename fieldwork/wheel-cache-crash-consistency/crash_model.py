#!/usr/bin/env python3
"""Small state model for extracted-wheel cache publication protocols."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
from typing import Iterable


class Protocol(str, Enum):
    DIRECTORY_EXISTS = "directory-exists"
    MARKER_ONLY = "marker-only"
    DURABLE_MARKER = "durable-marker"
    VERIFY_CONTENTS = "verify-contents"


@dataclass(frozen=True)
class ArchiveState:
    directory_visible: bool = False
    metadata_bytes: int = 0
    module_bytes: int = 0
    marker_visible: bool = False
    data_durable: bool = False
    directory_durable: bool = False
    marker_durable: bool = False

    @property
    def complete(self) -> bool:
        return self.metadata_bytes > 0 and self.module_bytes > 0


def publish_steps(protocol: Protocol) -> list[ArchiveState]:
    state = ArchiveState()
    states = [state]

    # Extraction has completed in userspace/kernel buffers.
    state = replace(state, metadata_bytes=128, module_bytes=64)
    states.append(state)

    if protocol is Protocol.DURABLE_MARKER:
        state = replace(state, data_durable=True)
        states.append(state)

    # Rename makes the directory visible to readers.
    state = replace(state, directory_visible=True)
    states.append(state)

    if protocol is Protocol.DURABLE_MARKER:
        state = replace(state, directory_durable=True)
        states.append(state)

    if protocol in {Protocol.MARKER_ONLY, Protocol.DURABLE_MARKER}:
        state = replace(state, marker_visible=True)
        states.append(state)
        if protocol is Protocol.DURABLE_MARKER:
            state = replace(state, marker_durable=True)
            states.append(state)

    return states


def after_power_loss(state: ArchiveState) -> ArchiveState:
    """Model metadata surviving while unsynchronized file data is lost."""
    return ArchiveState(
        directory_visible=state.directory_visible,
        metadata_bytes=state.metadata_bytes if state.data_durable else 0,
        module_bytes=state.module_bytes if state.data_durable else 0,
        marker_visible=state.marker_visible,
        data_durable=state.data_durable,
        directory_durable=state.directory_durable,
        marker_durable=state.marker_durable,
    )


def trusted(protocol: Protocol, state: ArchiveState) -> bool:
    if protocol is Protocol.DIRECTORY_EXISTS:
        return state.directory_visible
    if protocol in {Protocol.MARKER_ONLY, Protocol.DURABLE_MARKER}:
        return state.directory_visible and state.marker_visible
    if protocol is Protocol.VERIFY_CONTENTS:
        return state.directory_visible and state.complete
    raise AssertionError(protocol)


def cases(protocol: Protocol) -> Iterable[dict[str, object]]:
    for crash_point, state in enumerate(publish_steps(protocol)):
        for crash_kind, observed in (
            ("process-exit", state),
            ("power-loss", after_power_loss(state)),
        ):
            yield {
                "protocol": protocol.value,
                "crash_point": crash_point,
                "crash_kind": crash_kind,
                "directory_visible": observed.directory_visible,
                "marker_visible": observed.marker_visible,
                "metadata_bytes": observed.metadata_bytes,
                "module_bytes": observed.module_bytes,
                "trusted": trusted(protocol, observed),
                "complete": observed.complete,
                "unsafe_trust": trusted(protocol, observed) and not observed.complete,
            }


def main() -> None:
    rows = [row for protocol in Protocol for row in cases(protocol)]

    # Directory-existence trust admits a visible, incomplete archive.
    assert any(
        row["protocol"] == Protocol.DIRECTORY_EXISTS.value and row["unsafe_trust"]
        for row in rows
    )

    # A marker without durable data is insufficient in the general model.
    marker_survived = ArchiveState(
        directory_visible=True,
        marker_visible=True,
        metadata_bytes=0,
        module_bytes=0,
        directory_durable=True,
        marker_durable=True,
        data_durable=False,
    )
    assert trusted(Protocol.MARKER_ONLY, marker_survived)
    assert not marker_survived.complete

    # Durable data + directory + marker never trusts an incomplete archive.
    assert not any(
        row["protocol"] == Protocol.DURABLE_MARKER.value and row["unsafe_trust"]
        for row in rows
    )

    # Full validation rejects incomplete contents even when the directory exists.
    assert not any(
        row["protocol"] == Protocol.VERIFY_CONTENTS.value and row["unsafe_trust"]
        for row in rows
    )

    summary = {
        protocol.value: {
            "cases": sum(row["protocol"] == protocol.value for row in rows),
            "unsafe_trust_cases": sum(
                row["protocol"] == protocol.value and row["unsafe_trust"] for row in rows
            ),
        }
        for protocol in Protocol
    }
    print(json.dumps({"summary": summary, "cases": rows}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
