use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use walkdir::WalkDir;

use uv_cache::{ARCHIVE_VERSION, ArchiveId, Cache};
use uv_distribution_filename::WheelFilename;
use uv_distribution_types::Hashed;
use uv_fs::PortablePath;
use uv_pypi_types::{HashDigest, HashDigests};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
struct ArchiveMember {
    path: String,
    size: u64,
}

impl ArchiveMember {
    fn new(path: &Path, size: u64) -> Self {
        Self {
            path: PortablePath::from(path).to_string(),
            size,
        }
    }
}

/// An archive (unzipped wheel) that exists in the local cache.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Archive {
    /// The unique ID of the entry in the wheel's archive bucket.
    pub id: ArchiveId,
    /// The computed hashes of the archive.
    pub hashes: HashDigests,
    /// The filename of the wheel.
    pub filename: WheelFilename,
    /// The version of the archive bucket.
    pub version: u8,
    /// The size of the downloaded archive.
    #[serde(default)]
    pub size: Option<u64>,
    /// Trusted extracted members recorded when the wheel was unpacked.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    members: Option<Vec<ArchiveMember>>,
}

impl Archive {
    /// Create a new [`Archive`] with the given ID and hashes.
    pub(crate) fn new(
        id: ArchiveId,
        hashes: HashDigests,
        filename: WheelFilename,
        size: Option<u64>,
        members: Vec<(PathBuf, u64)>,
    ) -> Self {
        let members = members
            .into_iter()
            .map(|(path, size)| ArchiveMember::new(&path, size))
            .collect();
        Self {
            id,
            hashes,
            filename,
            version: ARCHIVE_VERSION,
            size,
            members: Some(members),
        }
    }

    /// Returns `true` if the archive exists and its recorded members match.
    pub fn exists(&self, cache: &Cache) -> bool {
        if self.version != ARCHIVE_VERSION {
            return false;
        }
        let root = cache.archive(&self.id);
        if !root.is_dir() {
            return false;
        }
        let Some(expected) = self.members.as_ref() else {
            return true;
        };
        let mut actual = BTreeMap::new();
        for entry in WalkDir::new(&root).follow_links(false).min_depth(1) {
            let Ok(entry) = entry else {
                return false;
            };
            if entry.file_type().is_dir() {
                continue;
            }
            if !entry.file_type().is_file() {
                return false;
            }
            let Ok(relative) = entry.path().strip_prefix(&root) else {
                return false;
            };
            let Ok(metadata) = entry.metadata() else {
                return false;
            };
            actual.insert(PortablePath::from(relative).to_string(), metadata.len());
        }
        actual.len() == expected.len()
            && expected
                .iter()
                .all(|member| actual.get(&member.path) == Some(&member.size))
    }
}

impl Hashed for Archive {
    fn hashes(&self) -> &[HashDigest] {
        self.hashes.as_slice()
    }
}

#[cfg(test)]
mod tests {
    use std::str::FromStr;

    use super::*;

    #[test]
    fn deserialize_legacy_archive() {
        #[derive(serde::Serialize)]
        struct LegacyArchive {
            id: ArchiveId,
            hashes: HashDigests,
            filename: WheelFilename,
            version: u8,
        }

        let legacy = LegacyArchive {
            id: ArchiveId::default(),
            hashes: HashDigests::empty(),
            filename: WheelFilename::from_str("iniconfig-2.0.0-py3-none-any.whl")
                .expect("valid wheel filename"),
            version: ARCHIVE_VERSION,
        };
        let bytes = rmp_serde::to_vec(&legacy).expect("serialize legacy archive");
        let archive: Archive = rmp_serde::from_slice(&bytes).expect("deserialize legacy archive");

        assert_eq!(archive.size, None);
        assert!(archive.members.is_none());
    }

    fn archive_with_members(cache: &Cache, members: &[(&str, &[u8])]) -> Archive {
        let id = ArchiveId::default();
        let root = cache.archive(&id);
        for (relative, contents) in members {
            let path = root.join(relative);
            fs_err::create_dir_all(path.parent().expect("member has parent")).unwrap();
            fs_err::write(path, contents).unwrap();
        }
        Archive::new(
            id,
            HashDigests::empty(),
            WheelFilename::from_str("iniconfig-2.0.0-py3-none-any.whl")
                .expect("valid wheel filename"),
            None,
            members
                .iter()
                .map(|(relative, contents)| (PathBuf::from(relative), contents.len() as u64))
                .collect(),
        )
    }

    #[test]
    fn validates_recorded_members() {
        let cache = Cache::temp().unwrap();
        let archive = archive_with_members(
            &cache,
            &[
                ("package/__init__.py", b"VALUE = 1\n"),
                ("package.dist-info/METADATA", b"Name: package\n"),
            ],
        );
        assert!(archive.exists(&cache));
    }

    #[test]
    fn rejects_missing_member() {
        let cache = Cache::temp().unwrap();
        let archive = archive_with_members(
            &cache,
            &[
                ("package/__init__.py", b"VALUE = 1\n"),
                ("package.dist-info/METADATA", b"Name: package\n"),
            ],
        );
        fs_err::remove_file(cache.archive(&archive.id).join("package/__init__.py")).unwrap();
        assert!(!archive.exists(&cache));
    }

    #[test]
    fn rejects_unexpected_member() {
        let cache = Cache::temp().unwrap();
        let archive = archive_with_members(
            &cache,
            &[
                ("package/__init__.py", b"VALUE = 1\n"),
                ("package.dist-info/METADATA", b"Name: package\n"),
            ],
        );
        fs_err::write(cache.archive(&archive.id).join("unexpected.py"), b"pass\n").unwrap();
        assert!(!archive.exists(&cache));
    }

    #[test]
    fn rejects_size_mismatch() {
        let cache = Cache::temp().unwrap();
        let archive = archive_with_members(
            &cache,
            &[
                ("package/__init__.py", b"VALUE = 1\n"),
                ("package.dist-info/METADATA", b"Name: package\n"),
            ],
        );
        fs_err::write(
            cache.archive(&archive.id).join("package/__init__.py"),
            b"VALUE = 1000\n",
        )
        .unwrap();
        assert!(!archive.exists(&cache));
    }
}
