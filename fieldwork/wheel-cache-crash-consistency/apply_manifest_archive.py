#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv-distribution/src/archive.rs"
text = path.read_text()

def replace(old: str, new: str) -> None:
    global text
    if text.count(old) != 1:
        raise SystemExit(f"archive fragment mismatch: {old[:80]!r}")
    text = text.replace(old, new)

replace(
    "use uv_cache::{ARCHIVE_VERSION, ArchiveId, Cache};\n",
    "use std::collections::BTreeMap;\n"
    "use std::path::{Path, PathBuf};\n\n"
    "use walkdir::WalkDir;\n\n"
    "use uv_cache::{ARCHIVE_VERSION, ArchiveId, Cache};\n"
    "use uv_fs::PortablePath;\n",
)
replace(
    "/// An archive (unzipped wheel) that exists in the local cache.\n",
    "#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]\n"
    "struct ArchiveMember {\n"
    "    path: String,\n"
    "    size: u64,\n"
    "}\n\n"
    "impl ArchiveMember {\n"
    "    fn new(path: &Path, size: u64) -> Self {\n"
    "        Self {\n"
    "            path: PortablePath::from(path).to_string(),\n"
    "            size,\n"
    "        }\n"
    "    }\n"
    "}\n\n"
    "/// An archive (unzipped wheel) that exists in the local cache.\n",
)
replace(
    "    /// The size of the downloaded archive.\n"
    "    #[serde(default)]\n"
    "    pub size: Option<u64>,\n"
    "}\n",
    "    /// The size of the downloaded archive.\n"
    "    #[serde(default)]\n"
    "    pub size: Option<u64>,\n"
    "    /// Trusted extracted members recorded when the wheel was unpacked.\n"
    "    #[serde(default, skip_serializing_if = \"Option::is_none\")]\n"
    "    members: Option<Vec<ArchiveMember>>,\n"
    "}\n",
)
replace(
    "        size: Option<u64>,\n"
    "    ) -> Self {\n"
    "        Self {\n"
    "            id,\n"
    "            hashes,\n"
    "            filename,\n"
    "            version: ARCHIVE_VERSION,\n"
    "            size,\n"
    "        }\n"
    "    }\n",
    "        size: Option<u64>,\n"
    "        members: Vec<(PathBuf, u64)>,\n"
    "    ) -> Self {\n"
    "        let members = members\n"
    "            .into_iter()\n"
    "            .map(|(path, size)| ArchiveMember::new(&path, size))\n"
    "            .collect();\n"
    "        Self {\n"
    "            id,\n"
    "            hashes,\n"
    "            filename,\n"
    "            version: ARCHIVE_VERSION,\n"
    "            size,\n"
    "            members: Some(members),\n"
    "        }\n"
    "    }\n",
)
replace(
    "    /// Returns `true` if the archive exists in the cache.\n"
    "    pub fn exists(&self, cache: &Cache) -> bool {\n"
    "        self.version == ARCHIVE_VERSION && cache.archive(&self.id).exists()\n"
    "    }\n",
    "    /// Returns `true` if the archive exists and its recorded members match.\n"
    "    pub fn exists(&self, cache: &Cache) -> bool {\n"
    "        if self.version != ARCHIVE_VERSION {\n"
    "            return false;\n"
    "        }\n"
    "        let root = cache.archive(&self.id);\n"
    "        if !root.is_dir() {\n"
    "            return false;\n"
    "        }\n"
    "        let Some(expected) = self.members.as_ref() else {\n"
    "            return true;\n"
    "        };\n"
    "        let mut actual = BTreeMap::new();\n"
    "        for entry in WalkDir::new(&root).follow_links(false).min_depth(1) {\n"
    "            let Ok(entry) = entry else {\n"
    "                return false;\n"
    "            };\n"
    "            if entry.file_type().is_dir() {\n"
    "                continue;\n"
    "            }\n"
    "            if !entry.file_type().is_file() {\n"
    "                return false;\n"
    "            }\n"
    "            let Ok(relative) = entry.path().strip_prefix(&root) else {\n"
    "                return false;\n"
    "            };\n"
    "            let Ok(metadata) = entry.metadata() else {\n"
    "                return false;\n"
    "            };\n"
    "            actual.insert(PortablePath::from(relative).to_string(), metadata.len());\n"
    "        }\n"
    "        actual.len() == expected.len()\n"
    "            && expected\n"
    "                .iter()\n"
    "                .all(|member| actual.get(&member.path) == Some(&member.size))\n"
    "    }\n",
)
path.write_text(text)
