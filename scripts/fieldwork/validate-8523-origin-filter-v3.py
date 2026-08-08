#!/usr/bin/env python3
import argparse
import importlib.util
import pathlib
import sys

V2_PATH = pathlib.Path(__file__).with_name("validate_v2.py")
spec = importlib.util.spec_from_file_location("fieldwork_8523_v2", V2_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("failed to load v2 validator")
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
base = v2.base


def mixed_modern_origins(transcript, root, uv):
    transcript.write("===== mixed modern config + CLI indexes =====\n")
    _, config, tool_dir, bin_dir, env = base.scenario_env(root, "mixed-modern")
    server = base.IndexServer(root / "mixed-modern-index", authenticated=False)
    try:
        config_endpoint = server.endpoint("/secondary/simple")
        cli_endpoint = server.endpoint("/simple")
        base.write_config(
            config,
            "\n".join(
                [
                    "[[index]]",
                    'name = "config-owned"',
                    f'url = "{config_endpoint}"',
                    "default = true",
                    "",
                ]
            ),
        )
        installed = base.run(
            transcript,
            env,
            uv,
            "tool",
            "install",
            "--python",
            sys.executable,
            "--index",
            cli_endpoint,
            base.PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("mixed-origin install failed")

        installed_receipt = base.receipt(tool_dir)
        if config_endpoint in installed_receipt:
            raise RuntimeError("config-owned modern index survived mixed receipt filtering")
        if cli_endpoint not in installed_receipt:
            raise RuntimeError("adjacent CLI modern index was dropped from mixed receipt")
        if "0.1.0" not in base.public_version(bin_dir):
            raise RuntimeError("mixed-origin install did not publish 0.1.0")

        config.unlink()
        server.versions = ["0.1.0", "0.2.0"]
        base.assert_upgrade(transcript, env, uv, bin_dir)
        transcript.write("mixed_modern_origins=true\n")
    finally:
        server.close()


def tool_run_reuses_with_live_config(transcript, root, uv):
    transcript.write("===== tool run reuse with live config-origin index =====\n")
    _, config, tool_dir, _, env = base.scenario_env(root, "tool-run-reuse")
    server = base.IndexServer(root / "tool-run-reuse-index", authenticated=False)
    try:
        endpoint = server.endpoint("/simple")
        base.write_config(config, f'index-url = "{endpoint}"\n')
        installed = base.run(
            transcript,
            env,
            uv,
            "tool",
            "install",
            "--python",
            sys.executable,
            base.PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("tool-run reuse install failed")
        if endpoint in base.receipt(tool_dir):
            raise RuntimeError("config-origin index leaked into tool-run reuse receipt")

        request_start = len(server.requests)
        invoked = base.run(
            transcript,
            env,
            uv,
            "tool",
            "run",
            "--from",
            base.PACKAGE,
            base.PACKAGE,
        )
        if invoked.returncode != 0:
            raise RuntimeError("tool run failed")
        if "fieldwork-demo-tool 0.1.0" not in invoked.stdout:
            raise RuntimeError(f"tool run did not execute installed 0.1.0: {invoked.stdout}")
        requests_after = len(server.requests) - request_start
        transcript.write(f"tool_run_index_requests={requests_after}\n")
        if requests_after != 0:
            raise RuntimeError("tool run hit the index instead of reusing the installed environment")
        transcript.write("tool_run_reuse=true\n")
    finally:
        server.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", required=True, type=pathlib.Path)
    parser.add_argument("--root", required=True, type=pathlib.Path)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    transcript_path = args.root / "transcript.txt"
    with transcript_path.open("w", encoding="utf-8") as transcript:
        transcript.write(f"uv={args.uv}\n")
        v2.legacy_config_rotation(transcript, args.root, args.uv)
        base.legacy_cli_durable(transcript, args.root, args.uv)
        base.modern_config_refresh(transcript, args.root, args.uv)
        base.modern_cli_durable(transcript, args.root, args.uv)
        v2.config_find_links_unchanged(transcript, args.root, args.uv)
        mixed_modern_origins(transcript, args.root, args.uv)
        tool_run_reuses_with_live_config(transcript, args.root, args.uv)
        transcript.write(
            "VALIDATED: registry-index origin filtering preserves refreshed config, explicit CLI durability, mixed-list filtering, find-links behavior, and installed tool-run reuse\n"
        )
        transcript.flush()


if __name__ == "__main__":
    main()
