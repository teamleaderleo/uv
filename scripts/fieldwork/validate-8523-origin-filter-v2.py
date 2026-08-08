#!/usr/bin/env python3
import argparse
import importlib.util
import pathlib
import sys

BASE_PATH = pathlib.Path(__file__).with_name("validate_base.py")
spec = importlib.util.spec_from_file_location("fieldwork_8523_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("failed to load base validator")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def legacy_config_rotation(transcript, root, uv):
    transcript.write("===== legacy user-config credential rotation =====\n")
    _, config, tool_dir, bin_dir, env = base.scenario_env(root, "legacy-config")
    server = base.IndexServer(root / "legacy-config-index", authenticated=True)
    try:
        base.write_config(
            config,
            "\n".join(
                [
                    f'index-url = "{server.endpoint("/simple", base.OLD_TOKEN)}"',
                    f'extra-index-url = ["{server.endpoint("/extra", base.OLD_TOKEN)}"]',
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
            "--compile-bytecode",
            base.PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("legacy config install failed")
        installed_receipt = base.receipt(tool_dir)
        endpoint_prefix = f"127.0.0.1:{server.port}"
        if f"{endpoint_prefix}/simple" in installed_receipt:
            raise RuntimeError("config-origin index-url leaked into tool receipt")
        if f"{endpoint_prefix}/extra" in installed_receipt:
            raise RuntimeError("config-origin extra-index-url leaked into tool receipt")
        if "compile-bytecode = true" not in installed_receipt:
            raise RuntimeError("non-index receipt option was unexpectedly removed")
        if "0.1.0" not in base.public_version(bin_dir):
            raise RuntimeError("legacy config install did not publish 0.1.0")

        server.token = base.NEW_TOKEN
        server.versions = ["0.1.0", "0.2.0"]
        base.write_config(
            config,
            "\n".join(
                [
                    f'index-url = "{server.endpoint("/simple", base.NEW_TOKEN)}"',
                    f'extra-index-url = ["{server.endpoint("/extra", base.NEW_TOKEN)}"]',
                    "",
                ]
            ),
        )
        request_start = len(server.requests)
        base.assert_upgrade(transcript, env, uv, bin_dir)
        rotated_requests = server.requests[request_start:]
        if not any(
            authorized and expected == "new" and presented == "new"
            for _, _, authorized, expected, presented in rotated_requests
        ):
            raise RuntimeError("upgrade never used refreshed user-config credentials")
        transcript.write("legacy_config_rotation=true\n")
    finally:
        server.close()


def config_find_links_unchanged(transcript, root, uv):
    transcript.write("===== config find-links remains durable (untracked provenance) =====\n")
    _, config, tool_dir, bin_dir, env = base.scenario_env(root, "config-find-links")
    server = base.IndexServer(root / "config-find-links-index", authenticated=False)
    try:
        simple = server.endpoint("/simple")
        flat = server.endpoint("/flat")
        base.write_config(
            config,
            "\n".join(
                [
                    f'index-url = "{simple}"',
                    f'find-links = ["{flat}"]',
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
            base.PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("find-links control install failed")
        installed_receipt = base.receipt(tool_dir)
        if f"127.0.0.1:{server.port}/simple" in installed_receipt:
            raise RuntimeError("config-origin index-url leaked in find-links control")
        if f"127.0.0.1:{server.port}/flat" not in installed_receipt:
            raise RuntimeError("find-links persistence changed despite lacking origin metadata")
        server.versions = ["0.1.0", "0.2.0"]
        base.assert_upgrade(transcript, env, uv, bin_dir)
        transcript.write("config_find_links_unchanged=true\n")
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
        legacy_config_rotation(transcript, args.root, args.uv)
        base.legacy_cli_durable(transcript, args.root, args.uv)
        base.modern_config_refresh(transcript, args.root, args.uv)
        base.modern_cli_durable(transcript, args.root, args.uv)
        config_find_links_unchanged(transcript, args.root, args.uv)
        transcript.write(
            "VALIDATED: config-origin registry indexes are rediscovered; explicit CLI indexes and find-links persistence remain durable\n"
        )
        transcript.flush()


if __name__ == "__main__":
    main()
