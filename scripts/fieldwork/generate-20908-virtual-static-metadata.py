#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

path = Path("crates/uv-distribution/src/source/mod.rs")
text = path.read_text()

old_enum = '''enum StaticMetadata {
    /// The metadata was found and successfully read.
    Some(ResolutionMetadata),
    /// The metadata was found, but it was ignored due to a dynamic version.
    Dynamic,
    /// The metadata was not found.
    None,
}
'''
new_enum = '''enum StaticMetadata {
    /// The metadata was found and successfully read.
    Some(ResolutionMetadata),
    /// The metadata was found, but it was ignored due to a dynamic version.
    Dynamic,
    /// Static project metadata was present, but one of its required fields could not be used.
    ///
    /// Ordinary packages may still obtain equivalent metadata from their build backend. Virtual
    /// projects cannot: `tool.uv.package = false` means their build system is ignored.
    Unavailable {
        error: uv_pypi_types::MetadataError,
        dynamic: bool,
    },
    /// The metadata was not found.
    None,
}
'''
if text.count(old_enum) != 1:
    raise SystemExit(f"unexpected StaticMetadata enum count: {text.count(old_enum)}")
text = text.replace(old_enum, new_enum)

old_dynamic = '''        let dynamic = pyproject_toml.as_ref().is_some_and(|pyproject_toml| {
            pyproject_toml.project.as_ref().is_some_and(|project| {
                project
                    .dynamic
                    .as_ref()
                    .is_some_and(|dynamic| dynamic.iter().any(|field| field == "version"))
            })
        });

        // Attempt to read static metadata from the `pyproject.toml`.
'''
new_dynamic = '''        let dynamic = pyproject_toml.as_ref().is_some_and(|pyproject_toml| {
            pyproject_toml.project.as_ref().is_some_and(|project| {
                project
                    .dynamic
                    .as_ref()
                    .is_some_and(|dynamic| dynamic.iter().any(|field| field == "version"))
            })
        });
        let mut unavailable = None;

        // Attempt to read static metadata from the `pyproject.toml`.
'''
if text.count(old_dynamic) != 1:
    raise SystemExit(f"unexpected dynamic metadata anchor count: {text.count(old_dynamic)}")
text = text.replace(old_dynamic, new_dynamic)

old_soft = '''                Err(
                    err @ (uv_pypi_types::MetadataError::Pep508Error(_)
                    | uv_pypi_types::MetadataError::DynamicField(_)
                    | uv_pypi_types::MetadataError::FieldNotFound(_)
                    | uv_pypi_types::MetadataError::PoetrySyntax),
                ) => {
                    debug!("No static `pyproject.toml` available for: {source} ({err:?})");
                }
'''
new_soft = '''                Err(
                    err @ (uv_pypi_types::MetadataError::Pep508Error(_)
                    | uv_pypi_types::MetadataError::DynamicField(_)
                    | uv_pypi_types::MetadataError::FieldNotFound(_)
                    | uv_pypi_types::MetadataError::PoetrySyntax),
                ) => {
                    debug!("No static `pyproject.toml` available for: {source} ({err:?})");
                    unavailable = Some(err);
                }
'''
if text.count(old_soft) != 1:
    raise SystemExit(f"unexpected soft metadata error anchor count: {text.count(old_soft)}")
text = text.replace(old_soft, new_soft)

old_source_tree = '''        if source.is_source_tree() {
            return Ok(if dynamic { Self::Dynamic } else { Self::None });
        }
'''
new_source_tree = '''        if source.is_source_tree() {
            return Ok(match unavailable {
                Some(error) => Self::Unavailable { error, dynamic },
                None if dynamic => Self::Dynamic,
                None => Self::None,
            });
        }
'''
if text.count(old_source_tree) != 1:
    raise SystemExit(f"unexpected source-tree return count: {text.count(old_source_tree)}")
text = text.replace(old_source_tree, new_source_tree)

start = text.index("    async fn source_tree_metadata(")
end = text.index("    /// Build a source distribution from a Git repository.", start)
section = text[start:end]
old_match = '''            StaticMetadata::Dynamic => true,
            StaticMetadata::None => false,
'''
new_match = '''            StaticMetadata::Unavailable { error, dynamic } => {
                if matches!(
                    source,
                    BuildableSource::Dist(SourceDist::Directory(dist))
                        if dist.r#virtual.unwrap_or(false)
                ) {
                    return Err(Error::PyprojectToml(error));
                }
                dynamic
            }
            StaticMetadata::Dynamic => true,
            StaticMetadata::None => false,
'''
if section.count(old_match) != 1:
    raise SystemExit(f"unexpected source-tree metadata match count: {section.count(old_match)}")
section = section.replace(old_match, new_match)

pattern = re.compile(
    r'(?P<indent>[ \t]+)StaticMetadata::Dynamic => true,\n(?P=indent)StaticMetadata::None => false,'
)

def add_unavailable(match: re.Match[str]) -> str:
    indent = match.group("indent")
    return (
        f"{indent}StaticMetadata::Unavailable {{ dynamic, .. }} => dynamic,\n"
        f"{indent}StaticMetadata::Dynamic => true,\n"
        f"{indent}StaticMetadata::None => false,"
    )

# Do not run the generic rewrite through `source_tree_metadata`: that function needs the special
# virtual-project behavior above. The remaining four match sites are ordinary package/archive/Git
# paths and keep their existing fallback semantics.
prefix, prefix_count = pattern.subn(add_unavailable, text[:start])
suffix, suffix_count = pattern.subn(add_unavailable, text[end:])
count = prefix_count + suffix_count
if count != 4:
    raise SystemExit(f"expected four ordinary StaticMetadata match sites, found {count}")
text = prefix + section + suffix

path.write_text(text)
