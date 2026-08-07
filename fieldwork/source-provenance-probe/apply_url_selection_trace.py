from __future__ import annotations

from pathlib import Path


def replace_exact(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"expected one exact anchor in {path}, found {count}")
    path.write_text(content.replace(old, new))


path = Path("crates/uv-resolver/src/resolver/urls.rs")
old = '''        let mut regular: FxHashMap<PackageName, Vec<(VerbatimParsedUrl, bool)>> =
            FxHashMap::default();
        let mut overrides = ForkMap::default();

        // Add all direct regular requirements and constraints URL.
        for (requirement, root_context) in
            manifest.requirements_no_overrides_with_root_context(env, dependencies)
        {
            let Some(url) = requirement.source.to_verbatim_parsed_url() else {
                // Registry requirement
                continue;
            };

            let package_urls = regular.entry(requirement.name.clone()).or_default();
            if let Some((package_url, package_root_context)) =
                package_urls.iter_mut().find(|(package_url, _)| {
                    same_resource(&package_url.parsed_url, &url.parsed_url, git)
                })
            {
                let previous_editable = package_url.is_editable();
                let incoming_editable = url.is_editable();
                let both_directories = matches!(
                    (&package_url.parsed_url, &url.parsed_url),
                    (ParsedUrl::Directory(_), ParsedUrl::Directory(_))
                );

                // Root requirements and user constraints determine directory presentation over
                // equivalent lookahead metadata. Editability is merged independently below.
                let keep_existing = if both_directories {
                    match (*package_root_context, root_context) {
                        (true, false) => true,
                        (false, true) => false,
                        _ => previous_editable && !incoming_editable,
                    }
                } else {
                    false
                };

                if !keep_existing {
                    *package_url = url;
                    *package_root_context = root_context;
                }

                if (previous_editable || incoming_editable)
                    && let VerbatimParsedUrl {
                        parsed_url: ParsedUrl::Directory(ParsedDirectoryUrl { editable, .. }),
                        verbatim: _,
                    } = package_url
                    && editable.is_none()
                {
                    debug!("Allowing an editable variant of {}", &package_url.verbatim);
                    *editable = Some(true);
                }
            } else {
                package_urls.push((url, root_context));
            }
        }

        let mut regular = regular
            .into_iter()
            .map(|(name, urls)| {
                (
                    name,
                    urls.into_iter().map(|(url, _root_context)| url).collect(),
                )
            })
            .collect::<FxHashMap<_, _>>();

        // Add all URLs from overrides. If there is an override URL, all other URLs from
'''
new = '''        let mut regular: FxHashMap<PackageName, Vec<(VerbatimParsedUrl, bool)>> =
            FxHashMap::default();
        let mut overrides = ForkMap::default();

        // Add all direct regular requirements and constraints URL.
        for (requirement, root_context) in
            manifest.requirements_no_overrides_with_root_context(env, dependencies)
        {
            let Some(url) = requirement.source.to_verbatim_parsed_url() else {
                // Registry requirement
                continue;
            };

            let trace_child = requirement.name.as_str() == "child"
                && std::env::var_os("UV_FIELDWORK_URL_TRACE").is_some();
            if trace_child {
                eprintln!(
                    "FIELDWORK_URL_TRACE incoming lane={} given={:?} absolute={} editable={} parsed={:?}",
                    if root_context { "root" } else { "lookahead" },
                    url.verbatim.given(),
                    url.verbatim.was_given_absolute(),
                    url.is_editable(),
                    url.parsed_url,
                );
            }

            let package_urls = regular.entry(requirement.name.clone()).or_default();
            if let Some((package_url, package_root_context)) =
                package_urls.iter_mut().find(|(package_url, _)| {
                    same_resource(&package_url.parsed_url, &url.parsed_url, git)
                })
            {
                // Preserve exact draft #304 merge behavior; the sidecar is diagnostic only.
                if package_url.is_editable()
                    && let VerbatimParsedUrl {
                        parsed_url: ParsedUrl::Directory(ParsedDirectoryUrl { editable, .. }),
                        verbatim: _,
                    } = &url
                    && editable.is_none()
                {
                    debug!("Allowing an editable variant of {}", &package_url.verbatim);
                } else {
                    *package_url = url;
                    *package_root_context = root_context;
                }
                if trace_child {
                    eprintln!(
                        "FIELDWORK_URL_TRACE retained lane={} given={:?} absolute={} editable={} parsed={:?}",
                        if *package_root_context { "root" } else { "lookahead" },
                        package_url.verbatim.given(),
                        package_url.verbatim.was_given_absolute(),
                        package_url.is_editable(),
                        package_url.parsed_url,
                    );
                }
            } else {
                if trace_child {
                    eprintln!("FIELDWORK_URL_TRACE retained=new");
                }
                package_urls.push((url, root_context));
            }
        }

        let mut regular = regular
            .into_iter()
            .map(|(name, urls)| {
                (
                    name,
                    urls.into_iter().map(|(url, _root_context)| url).collect(),
                )
            })
            .collect::<FxHashMap<_, _>>();

        // Add all URLs from overrides. If there is an override URL, all other URLs from
'''
replace_exact(path, old, new)
