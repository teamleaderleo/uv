from __future__ import annotations

from pathlib import Path


def replace_exact(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"expected one exact anchor in {path}, found {count}")
    path.write_text(content.replace(old, new))


manifest = Path("crates/uv-resolver/src/manifest.rs")
old_manifest = '''    /// Like [`Self::requirements`], but without the overrides.
    pub(crate) fn requirements_no_overrides<'a>(
        &'a self,
        env: &'a ResolverEnvironment,
        mode: DependencyMode,
    ) -> impl Iterator<Item = Cow<'a, Requirement>> + 'a {
        match mode {
            // Include all direct and transitive requirements, with constraints and overrides applied.
            DependencyMode::Transitive => Either::Left(
                self.lookaheads
                    .iter()
                    .flat_map(move |lookahead| {
                        self.overrides
                            .apply_for(
                                lookahead.package(),
                                lookahead.version(),
                                lookahead.requirements(),
                            )
                            .filter(|requirement| {
                                !self.excludes.contains_for(
                                    lookahead.package(),
                                    lookahead.version(),
                                    &requirement.name,
                                )
                            })
                            .filter(move |requirement| {
                                requirement
                                    .evaluate_markers(env.marker_environment(), lookahead.extras())
                            })
                    })
                    .chain(
                        self.overrides
                            .apply(&self.requirements)
                            .filter(|requirement| !self.excludes.contains(&requirement.name))
                            .filter(move |requirement| {
                                requirement.evaluate_markers(env.marker_environment(), &[])
                            }),
                    )
                    .chain(
                        self.constraints
                            .requirements()
                            .filter(|requirement| !self.excludes.contains(&requirement.name))
                            .filter(move |requirement| {
                                requirement.evaluate_markers(env.marker_environment(), &[])
                            })
                            .map(Cow::Borrowed),
                    ),
            ),
            // Include direct requirements, with constraints and overrides applied.
            DependencyMode::Direct => Either::Right(
                self.overrides
                    .apply(&self.requirements)
                    .chain(self.constraints.requirements().map(Cow::Borrowed))
                    .filter(|requirement| !self.excludes.contains(&requirement.name))
                    .filter(move |requirement| {
                        requirement.evaluate_markers(env.marker_environment(), &[])
                    }),
            ),
        }
    }
'''
new_manifest = '''    /// Like [`Self::requirements`], but without the overrides.
    pub(crate) fn requirements_no_overrides<'a>(
        &'a self,
        env: &'a ResolverEnvironment,
        mode: DependencyMode,
    ) -> impl Iterator<Item = Cow<'a, Requirement>> + 'a {
        self.requirements_no_overrides_with_root_context(env, mode)
            .map(|(requirement, _root_context)| requirement)
    }

    /// Like [`Self::requirements_no_overrides`], retaining whether a requirement came from the
    /// root input lane rather than lookahead metadata.
    pub(crate) fn requirements_no_overrides_with_root_context<'a>(
        &'a self,
        env: &'a ResolverEnvironment,
        mode: DependencyMode,
    ) -> impl Iterator<Item = (Cow<'a, Requirement>, bool)> + 'a {
        match mode {
            // Include all direct and transitive requirements, with constraints and overrides applied.
            DependencyMode::Transitive => Either::Left(
                self.lookaheads
                    .iter()
                    .flat_map(move |lookahead| {
                        self.overrides
                            .apply_for(
                                lookahead.package(),
                                lookahead.version(),
                                lookahead.requirements(),
                            )
                            .filter(|requirement| {
                                !self.excludes.contains_for(
                                    lookahead.package(),
                                    lookahead.version(),
                                    &requirement.name,
                                )
                            })
                            .filter(move |requirement| {
                                requirement
                                    .evaluate_markers(env.marker_environment(), lookahead.extras())
                            })
                            .map(|requirement| (requirement, false))
                    })
                    .chain(
                        self.overrides
                            .apply(&self.requirements)
                            .filter(|requirement| !self.excludes.contains(&requirement.name))
                            .filter(move |requirement| {
                                requirement.evaluate_markers(env.marker_environment(), &[])
                            })
                            .map(|requirement| (requirement, true)),
                    )
                    .chain(
                        self.constraints
                            .requirements()
                            .filter(|requirement| !self.excludes.contains(&requirement.name))
                            .filter(move |requirement| {
                                requirement.evaluate_markers(env.marker_environment(), &[])
                            })
                            .map(|requirement| (Cow::Borrowed(requirement), true)),
                    ),
            ),
            // Include direct requirements, with constraints and overrides applied.
            DependencyMode::Direct => Either::Right(
                self.overrides
                    .apply(&self.requirements)
                    .chain(self.constraints.requirements().map(Cow::Borrowed))
                    .filter(|requirement| !self.excludes.contains(&requirement.name))
                    .filter(move |requirement| {
                        requirement.evaluate_markers(env.marker_environment(), &[])
                    })
                    .map(|requirement| (requirement, true)),
            ),
        }
    }
'''
replace_exact(manifest, old_manifest, new_manifest)

urls = Path("crates/uv-resolver/src/resolver/urls.rs")
old_urls = '''        let mut regular: FxHashMap<PackageName, Vec<VerbatimParsedUrl>> = FxHashMap::default();
        let mut overrides = ForkMap::default();

        // Add all direct regular requirements and constraints URL.
        for requirement in manifest.requirements_no_overrides(env, dependencies) {
            let Some(url) = requirement.source.to_verbatim_parsed_url() else {
                // Registry requirement
                continue;
            };

            let package_urls = regular.entry(requirement.name.clone()).or_default();
            if let Some(package_url) = package_urls
                .iter_mut()
                .find(|package_url| same_resource(&package_url.parsed_url, &url.parsed_url, git))
            {
                // Allow editables to override non-editables.
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
                }
            } else {
                package_urls.push(url);
            }
        }

        // Add all URLs from overrides. If there is an override URL, all other URLs from
'''
new_urls = '''        let mut regular: FxHashMap<PackageName, Vec<(VerbatimParsedUrl, bool)>> =
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
replace_exact(urls, old_urls, new_urls)
