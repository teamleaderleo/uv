#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/uv-workspace/src/pyproject_mut.rs")
text = path.read_text()

old_loop = '''    for item in deps.iter_mut() {
        let decor = item.decor_mut();
        let mut prefix = String::new();

        for comment in find_comments(decor.prefix()).chain(find_comments(decor.suffix())) {
            match &comment.kind {
                CommentType::OwnLine => {
                    prefix.push_str(&indentation_prefix_str);
                }
                CommentType::EndOfLine { leading_whitespace } => {
                    prefix.push_str(leading_whitespace);
                }
            }
            prefix.push_str(&comment.text);
        }
        prefix.push_str(&indentation_prefix_str);
        decor.set_prefix(prefix);
        decor.set_suffix("");
    }

    deps.set_trailing(&{
        let mut comments = find_comments(Some(deps.trailing())).peekable();
'''
new_loop = '''    let last_index = deps.len().checked_sub(1);
    let mut last_suffix_comments = Vec::new();

    for (index, item) in deps.iter_mut().enumerate() {
        let decor = item.decor_mut();
        let mut prefix = String::new();
        let mut comments = find_comments(decor.prefix()).collect::<Vec<_>>();
        let suffix_comments = find_comments(decor.suffix()).collect::<Vec<_>>();

        // Without a trailing comma, toml_edit stores an end-of-line comment on the final array
        // value in that value's suffix. Once we add the trailing comma below, the comment belongs
        // in the array trailing decoration (after the comma), not in the value's prefix (before the
        // value). Moving the final suffix as a unit also preserves any own-line comments that follow
        // the final value.
        if Some(index) == last_index {
            last_suffix_comments.extend(suffix_comments);
        } else {
            comments.extend(suffix_comments);
        }

        for comment in comments {
            match &comment.kind {
                CommentType::OwnLine => {
                    prefix.push_str(&indentation_prefix_str);
                }
                CommentType::EndOfLine { leading_whitespace } => {
                    prefix.push_str(leading_whitespace);
                }
            }
            prefix.push_str(&comment.text);
        }
        prefix.push_str(&indentation_prefix_str);
        decor.set_prefix(prefix);
        decor.set_suffix("");
    }

    deps.set_trailing(&{
        let mut comments = last_suffix_comments
            .into_iter()
            .chain(find_comments(Some(deps.trailing())))
            .peekable();
'''
if text.count(old_loop) != 1:
    raise SystemExit(f"unexpected reformat loop count: {text.count(old_loop)}")
text = text.replace(old_loop, new_loop)

anchor = '''    #[test]
    fn reformat_preserves_inline_comment_without_padding() {
        let mut doc: DocumentMut = r#"\n[project]\ndependencies = [\n    \"attrs>=25.4.0\",#comment\n]\n"#
        .parse()
        .unwrap();

        reformat_array_multiline(
            doc["project"]["dependencies"]
                .as_array_mut()
                .expect("dependencies array"),
        );

        let serialized = doc.to_string();

        assert!(
            serialized.contains("\\\"attrs>=25.4.0\\\",#comment"),
            "inline comment spacing without padding should be preserved:\\n{serialized}"
        );
    }
'''
addition = anchor + '''

    #[test]
    fn add_optional_dependency_preserves_inline_comment_without_trailing_comma() -> Result<()> {
        let toml = r#"\n[project]\nname = \"grumblemuffins\"\nversion = \"0.1.0\"\nrequires-python = \">=3.11\"\n\n[project.optional-dependencies]\ntyping = [\n    \"pandas-stubs>=2.0.2\",\n    \"narwhals>=1.42.0\" # narwhals are toothed whales native to the Arctic\n]\n"#;
        let mut pyproject = PyProjectTomlMut::from_toml(toml, DependencyTarget::PyProjectToml)?;
        let group = ExtraName::from_str("typing")?;
        let requirement = Requirement::from_str("narwhals>=1.42")?;

        pyproject.add_optional_dependency(&group, &requirement, None, false)?;
        let serialized = pyproject.to_string();

        assert!(
            serialized.contains(
                "\\\"narwhals>=1.42\\\", # narwhals are toothed whales native to the Arctic"
            ),
            "inline comment should remain on the updated final dependency:\\n{serialized}"
        );
        assert!(
            !serialized.contains(
                "\\\"pandas-stubs>=2.0.2\\\", # narwhals are toothed whales native to the Arctic"
            ),
            "inline comment must not move to the preceding dependency:\\n{serialized}"
        );
        Ok(())
    }

    #[test]
    fn add_optional_dependency_preserves_inline_comment_with_trailing_comma() -> Result<()> {
        let toml = r#"\n[project]\nname = \"grumblemuffins\"\nversion = \"0.1.0\"\nrequires-python = \">=3.11\"\n\n[project.optional-dependencies]\ntyping = [\n    \"pandas-stubs>=2.0.2\",\n    \"narwhals>=1.42.0\", # narwhals are toothed whales native to the Arctic\n]\n"#;
        let mut pyproject = PyProjectTomlMut::from_toml(toml, DependencyTarget::PyProjectToml)?;
        let group = ExtraName::from_str("typing")?;
        let requirement = Requirement::from_str("narwhals>=1.42")?;

        pyproject.add_optional_dependency(&group, &requirement, None, false)?;
        let serialized = pyproject.to_string();

        assert!(
            serialized.contains(
                "\\\"narwhals>=1.42\\\", # narwhals are toothed whales native to the Arctic"
            ),
            "existing trailing-comma behavior should remain unchanged:\\n{serialized}"
        );
        Ok(())
    }
'''
if text.count(anchor) != 1:
    raise SystemExit(f"unexpected test anchor count: {text.count(anchor)}")
text = text.replace(anchor, addition)

path.write_text(text)
