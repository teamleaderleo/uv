#!/usr/bin/env python3
"""Add a test-only replay of pointer/link publication divergence."""

from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv-distribution/src/distribution_database.rs"
text = path.read_text(encoding="utf-8")

old = """#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_tar_zst_extension() {
"""
new = """#[cfg(test)]
mod tests {
    use std::str::FromStr;

    use super::*;

    #[tokio::test]
    async fn pointer_and_link_publication_can_diverge() {
        let cache = Cache::temp().unwrap();
        let wheel_entry = cache.entry(CacheBucket::Wheels, "generation-race", "wheel");
        let pointer_entry = wheel_entry.with_file("wheel.rev");

        let temp_a = tempfile::tempdir_in(cache.root()).unwrap();
        fs_err::write(temp_a.path().join("member-a"), b"a").unwrap();
        let id_a = cache
            .persist(temp_a.keep(), wheel_entry.path())
            .await
            .unwrap();

        let temp_b = tempfile::tempdir_in(cache.root()).unwrap();
        fs_err::write(temp_b.path().join("member-b"), b"b").unwrap();
        let id_b = cache
            .persist(temp_b.keep(), wheel_entry.path())
            .await
            .unwrap();

        // Replay a legal interleaving: publisher A writes its pointer after publisher B
        // has already replaced the wheel-entry link.
        let archive_a = Archive::new(
            id_a.clone(),
            HashDigests::empty(),
            WheelFilename::from_str("iniconfig-2.0.0-py3-none-any.whl").unwrap(),
            None,
            vec![(PathBuf::from("member-a"), 1)],
        );
        PathArchivePointer {
            timestamp: Timestamp::now(),
            archive: archive_a,
        }
        .write_to(&pointer_entry)
        .await
        .unwrap();

        let linked = cache.resolve_link(wheel_entry.path()).unwrap();
        let expected_link = fs_err::canonicalize(cache.archive(&id_b)).unwrap();
        assert_eq!(linked, expected_link);

        let pointed = PathArchivePointer::read_from(&pointer_entry)
            .unwrap()
            .unwrap()
            .into_archive();
        assert_eq!(pointed.id, id_a);
        assert_ne!(pointed.id, id_b);

        // Cache collection follows the wheel-entry link, not the .rev pointer. If the
        // unlinked A generation is retired, the pointer becomes stale while B remains live.
        fs_err::remove_dir_all(cache.archive(&pointed.id)).unwrap();
        assert!(!pointed.exists(&cache));
        assert!(cache.resolve_link(wheel_entry.path()).is_ok());
    }

    #[test]
    fn test_add_tar_zst_extension() {
"""

if text.count(old) != 1:
    raise SystemExit("generation-race test insertion point mismatch")
path.write_text(text.replace(old, new), encoding="utf-8")
print(path)
