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
replace(
    "        assert_eq!(archive.size, None);\n"
    "    }\n"
    "}\n",
    "        assert_eq!(archive.size, None);\n"
    "        assert!(archive.members.is_none());\n"
    "    }\n\n"
    "    fn archive_with_members(cache: &Cache, members: &[(&str, &[u8])]) -> Archive {\n"
    "        let id = ArchiveId::default();\n"
    "        let root = cache.archive(&id);\n"
    "        for (relative, contents) in members {\n"
    "            let path = root.join(relative);\n"
    "            fs_err::create_dir_all(path.parent().expect(\"member has parent\")).unwrap();\n"
    "            fs_err::write(path, contents).unwrap();\n"
    "        }\n"
    "        Archive::new(\n"
    "            id,\n"
    "            HashDigests::empty(),\n"
    "            WheelFilename::from_str(\"iniconfig-2.0.0-py3-none-any.whl\")\n"
    "                .expect(\"valid wheel filename\"),\n"
    "            None,\n"
    "            members\n"
    "                .iter()\n"
    "                .map(|(relative, contents)| {\n"
    "                    (PathBuf::from(relative), contents.len() as u64)\n"
    "                })\n"
    "                .collect(),\n"
    "        )\n"
    "    }\n\n"
    "    #[test]\n"
    "    fn validates_recorded_members() {\n"
    "        let cache = Cache::temp().unwrap();\n"
    "        let archive = archive_with_members(\n"
    "            &cache,\n"
    "            &[(\"package/__init__.py\", b\"VALUE = 1\\n\"), (\"package.dist-info/METADATA\", b\"Name: package\\n\")],\n"
    "        );\n"
    "        assert!(archive.exists(&cache));\n"
    "    }\n\n"
    "    #[test]\n"
    "    fn rejects_missing_member() {\n"
    "        let cache = Cache::temp().unwrap();\n"
    "        let archive = archive_with_members(\n"
    "            &cache,\n"
    "            &[(\"package/__init__.py\", b\"VALUE = 1\\n\"), (\"package.dist-info/METADATA\", b\"Name: package\\n\")],\n"
    "        );\n"
    "        fs_err::remove_file(cache.archive(&archive.id).join(\"package/__init__.py\")).unwrap();\n"
    "        assert!(!archive.exists(&cache));\n"
    "    }\n\n"
    "    #[test]\n"
    "    fn rejects_unexpected_member() {\n"
    "        let cache = Cache::temp().unwrap();\n"
    "        let archive = archive_with_members(\n"
    "            &cache,\n"
    "            &[(\"package/__init__.py\", b\"VALUE = 1\\n\"), (\"package.dist-info/METADATA\", b\"Name: package\\n\")],\n"
    "        );\n"
    "        fs_err::write(cache.archive(&archive.id).join(\"unexpected.py\"), b\"pass\\n\").unwrap();\n"
    "        assert!(!archive.exists(&cache));\n"
    "    }\n\n"
    "    #[test]\n"
    "    fn rejects_size_mismatch() {\n"
    "        let cache = Cache::temp().unwrap();\n"
    "        let archive = archive_with_members(\n"
    "            &cache,\n"
    "            &[(\"package/__init__.py\", b\"VALUE = 1\\n\"), (\"package.dist-info/METADATA\", b\"Name: package\\n\")],\n"
    "        );\n"
    "        fs_err::write(\n"
    "            cache.archive(&archive.id).join(\"package/__init__.py\"),\n"
    "            b\"VALUE = 1000\\n\",\n"
    "        )\n"
    "        .unwrap();\n"
    "        assert!(!archive.exists(&cache));\n"
    "    }\n"
    "}\n",
)
path.write_text(text)
