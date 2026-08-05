#!/usr/bin/env python3
"""Apply cross-platform pointer publication locks and a protocol test."""

from pathlib import Path
import sys

path = Path(sys.argv[1]) / "crates/uv-distribution/src/distribution_database.rs"
text = path.read_text(encoding="utf-8")

lock_guard = "        #[cfg(windows)]\n        let _lock = {"
if text.count(lock_guard) != 4:
    raise SystemExit(
        f"wheel publication lock-site mismatch: expected 4, found {text.count(lock_guard)}"
    )

# The first lock protects source-built, link-only publication. The demonstrated
# generation split requires both a wheel-entry link and a later .http/.rev pointer,
# so retain the existing platform behavior for that unrelated cache family and
# enable the remaining three pointer-producing locks on every platform.
first_lock = text.index(lock_guard)
prefix_end = first_lock + len(lock_guard)
text = text[:prefix_end] + text[prefix_end:].replace(
    lock_guard,
    "        let _lock = {",
)
if text.count(lock_guard) != 1:
    raise SystemExit("source-built link-only lock was not preserved exactly once")

old = """#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_tar_zst_extension() {
"""
new = """#[cfg(test)]
mod tests {
    use std::str::FromStr;
    use std::sync::Arc;

    use tokio::sync::oneshot;
    use uv_cache::Cache;

    use super::*;

    #[tokio::test]
    async fn wheel_publication_lock_serializes_link_and_pointer_updates() {
        let cache = Arc::new(Cache::temp().unwrap());
        let source = cache.root().join("source.whl");
        fs_err::write(&source, b"wheel").unwrap();
        let timestamp = Timestamp::from_path(&source).unwrap();
        let filename = WheelFilename::from_str("iniconfig-2.0.0-py3-none-any.whl").unwrap();

        let (a_persisted_tx, a_persisted_rx) = oneshot::channel();
        let (release_a_tx, release_a_rx) = oneshot::channel();
        let cache_a = Arc::clone(&cache);
        let filename_a = filename.clone();
        let publisher_a = tokio::spawn(async move {
            let wheel_entry =
                cache_a.entry(CacheBucket::Wheels, "generation-lock", "wheel");
            let lock_entry = wheel_entry.with_file("wheel.lock");
            let _lock = lock_entry.lock().await.unwrap();

            let temp = tempfile::tempdir_in(cache_a.root()).unwrap();
            fs_err::write(temp.path().join("member-a"), b"a").unwrap();
            let id = cache_a
                .persist(temp.keep(), wheel_entry.path())
                .await
                .unwrap();
            a_persisted_tx.send(()).unwrap();
            release_a_rx.await.unwrap();

            PathArchivePointer {
                timestamp,
                archive: Archive::new(
                    id.clone(),
                    HashDigests::empty(),
                    filename_a,
                    None,
                ),
            }
            .write_to(&wheel_entry.with_file("wheel.rev"))
            .await
            .unwrap();
            id
        });

        a_persisted_rx.await.unwrap();

        let (b_started_tx, b_started_rx) = oneshot::channel();
        let (b_acquired_tx, mut b_acquired_rx) = oneshot::channel();
        let cache_b = Arc::clone(&cache);
        let publisher_b = tokio::spawn(async move {
            let wheel_entry =
                cache_b.entry(CacheBucket::Wheels, "generation-lock", "wheel");
            b_started_tx.send(()).unwrap();
            let lock_entry = wheel_entry.with_file("wheel.lock");
            let _lock = lock_entry.lock().await.unwrap();
            b_acquired_tx.send(()).unwrap();

            let temp = tempfile::tempdir_in(cache_b.root()).unwrap();
            fs_err::write(temp.path().join("member-b"), b"b").unwrap();
            let id = cache_b
                .persist(temp.keep(), wheel_entry.path())
                .await
                .unwrap();
            PathArchivePointer {
                timestamp,
                archive: Archive::new(
                    id.clone(),
                    HashDigests::empty(),
                    filename,
                    None,
                ),
            }
            .write_to(&wheel_entry.with_file("wheel.rev"))
            .await
            .unwrap();
            id
        });

        b_started_rx.await.unwrap();
        tokio::task::yield_now().await;
        assert!(matches!(
            b_acquired_rx.try_recv(),
            Err(oneshot::error::TryRecvError::Empty)
        ));

        release_a_tx.send(()).unwrap();
        let id_a = publisher_a.await.unwrap();
        b_acquired_rx.await.unwrap();
        let id_b = publisher_b.await.unwrap();
        assert_ne!(id_a, id_b);

        let wheel_entry = cache.entry(CacheBucket::Wheels, "generation-lock", "wheel");
        let linked = cache.resolve_link(wheel_entry.path()).unwrap();
        assert_eq!(linked, fs_err::canonicalize(cache.archive(&id_b)).unwrap());

        let pointed = PathArchivePointer::read_from(wheel_entry.with_file("wheel.rev"))
            .unwrap()
            .unwrap()
            .into_archive();
        assert_eq!(pointed.id, id_b);
    }

    #[test]
    fn test_add_tar_zst_extension() {
"""
if text.count(old) != 1:
    raise SystemExit("generation lock test insertion point mismatch")
text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print(path)
