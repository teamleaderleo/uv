#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/uv-settings/src/settings.rs")
text = path.read_text()

anchor = '''}

impl From<ResolverInstallerOptions> for ToolOptions {
'''
replacement = '''}

/// Return whether an index endpoint should be persisted in a tool receipt.
///
/// Tool receipts intentionally outlive filesystem configuration. Persist explicit/legacy inputs,
/// but let user, system, and project configuration be rediscovered on later tool operations so
/// refreshed credentials and endpoint settings are not shadowed by the receipt.
fn tool_receipt_index_is_durable(origin: Option<Origin>) -> bool {
    !matches!(
        origin,
        Some(Origin::User | Origin::System | Origin::Project)
    )
}

impl From<ResolverInstallerOptions> for ToolOptions {
'''
if text.count(anchor) != 1:
    raise SystemExit(f"unexpected ToolOptions impl anchor count: {text.count(anchor)}")
text = text.replace(anchor, replacement)

old_index = '''            index: value.indexes.index.map(|indexes| {
                indexes
                    .into_iter()
                    .map(Index::with_promoted_auth_policy)
                    .collect()
            }),
            index_url: value.indexes.index_url,
            extra_index_url: value.indexes.extra_index_url,
            no_index: value.indexes.no_index,
            find_links: value.indexes.find_links,
'''
new_index = '''            index: value.indexes.index.and_then(|indexes| {
                let indexes = indexes
                    .into_iter()
                    .filter(|index| tool_receipt_index_is_durable(index.origin))
                    .map(Index::with_promoted_auth_policy)
                    .collect::<Vec<_>>();
                (!indexes.is_empty()).then_some(indexes)
            }),
            index_url: value.indexes.index_url.filter(|index| {
                let index: Index = index.clone().into();
                tool_receipt_index_is_durable(index.origin)
            }),
            extra_index_url: value.indexes.extra_index_url.and_then(|indexes| {
                let indexes = indexes
                    .into_iter()
                    .filter(|index| {
                        let index: Index = index.clone().into();
                        tool_receipt_index_is_durable(index.origin)
                    })
                    .collect::<Vec<_>>();
                (!indexes.is_empty()).then_some(indexes)
            }),
            no_index: value.indexes.no_index,
            find_links: value.indexes.find_links.and_then(|indexes| {
                let indexes = indexes
                    .into_iter()
                    .filter(|index| {
                        let index: Index = index.clone().into();
                        tool_receipt_index_is_durable(index.origin)
                    })
                    .collect::<Vec<_>>();
                (!indexes.is_empty()).then_some(indexes)
            }),
'''
if text.count(old_index) != 1:
    raise SystemExit(f"unexpected ToolOptions index block count: {text.count(old_index)}")
text = text.replace(old_index, new_index)

path.write_text(text)
