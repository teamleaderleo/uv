#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

path = Path("crates/uv-distribution/src/source/mod.rs")
text = path.read_text()

old = '''                Err(
                    err @ (uv_pypi_types::MetadataError::Pep508Error(_)
                    | uv_pypi_types::MetadataError::DynamicField(_)
                    | uv_pypi_types::MetadataError::FieldNotFound(_)
                    | uv_pypi_types::MetadataError::PoetrySyntax),
                ) => {
                    debug!("No static `pyproject.toml` available for: {source} ({err:?})");
                }
'''
new = '''                Err(
                    err @ (uv_pypi_types::MetadataError::Pep508Error(_)
                    | uv_pypi_types::MetadataError::DynamicField(_)
                    | uv_pypi_types::MetadataError::FieldNotFound(_)
                    | uv_pypi_types::MetadataError::PoetrySyntax),
                ) => {
                    // Virtual projects (`tool.uv.package = false`) do not use a build backend, so
                    // falling through to PEP 517 would only replace this useful project-metadata
                    // error with a misleading build failure. Ordinary packages retain the existing
                    // backend fallback behavior.
                    if matches!(
                        source,
                        BuildableSource::Dist(SourceDist::Directory(dist))
                            if dist.r#virtual.unwrap_or(false)
                    ) {
                        return Err(Error::PyprojectToml(err));
                    }
                    debug!("No static `pyproject.toml` available for: {source} ({err:?})");
                }
'''
if text.count(old) != 1:
    raise SystemExit(f"unexpected static pyproject soft-error arm count: {text.count(old)}")
text = text.replace(old, new)

path.write_text(text)
