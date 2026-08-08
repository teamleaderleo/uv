#!/usr/bin/env python3
import argparse
import base64
import contextlib
import http.server
import os
import pathlib
import subprocess
import sys
import threading
import zipfile

PACKAGE = "fieldwork-demo-tool"
MODULE = "fieldwork_demo_tool"
OLD_TOKEN = "old-token"
NEW_TOKEN = "new-token"


def basic_header(token: str) -> str:
    return "Basic " + base64.b64encode(f"aws:{token}".encode()).decode()


def build_wheel(root: pathlib.Path, version: str) -> pathlib.Path:
    wheel_name = f"{MODULE}-{version}-py3-none-any.whl"
    wheel_path = root / "packages" / wheel_name
    wheel_path.parent.mkdir(parents=True, exist_ok=True)
    dist_info = f"{MODULE}-{version}.dist-info"
    files = {
        f"{MODULE}/__init__.py": (
            "def main():\n"
            f"    print(\"{PACKAGE} {version}\")\n"
        ).encode(),
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {PACKAGE}\n"
            f"Version: {version}\n"
            "Requires-Python: >=3.9\n"
        ).encode(),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: fieldwork\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode(),
        f"{dist_info}/entry_points.txt": (
            "[console_scripts]\n"
            f"{PACKAGE} = {MODULE}:main\n"
        ).encode(),
    }
    record_path = f"{dist_info}/RECORD"
    files[record_path] = (
        "".join(f"{name},,\n" for name in files) + f"{record_path},,\n"
    ).encode()
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return wheel_path


class IndexServer:
    def __init__(self, root: pathlib.Path, authenticated: bool):
        self.root = root
        self.authenticated = authenticated
        self.token = OLD_TOKEN if authenticated else None
        self.versions = ["0.1.0"]
        self.wheels = {
            "0.1.0": build_wheel(root, "0.1.0"),
            "0.2.0": build_wheel(root, "0.2.0"),
        }
        self.requests = []
        old_header = basic_header(OLD_TOKEN)
        new_header = basic_header(NEW_TOKEN)
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *values):
                return

            def authorize(self):
                header = self.headers.get("Authorization")
                if header == old_header:
                    presented = "old"
                elif header == new_header:
                    presented = "new"
                elif header is None:
                    presented = "missing"
                else:
                    presented = "other"

                expected_generation = (
                    "new" if outer.token == NEW_TOKEN else "old"
                ) if outer.authenticated else "none"
                authorized = True
                if outer.authenticated:
                    expected = new_header if outer.token == NEW_TOKEN else old_header
                    authorized = header == expected
                outer.requests.append(
                    (self.command, self.path, authorized, expected_generation, presented)
                )
                if not authorized:
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="fieldwork"')
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return False
                return True

            def simple_response(self):
                body = "<html><body>" + "".join(
                    f'<a href="/packages/{outer.wheels[version].name}">{outer.wheels[version].name}</a>\n'
                    for version in outer.versions
                ) + "</body></html>"
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)

            def wheel_response(self, filename: str):
                for version in outer.versions:
                    wheel = outer.wheels[version]
                    if wheel.name == filename:
                        data = wheel.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        if self.command != "HEAD":
                            self.wfile.write(data)
                        return True
                return False

            def route(self):
                if not self.authorize():
                    return
                clean = self.path.rstrip("/")
                if clean in {
                    f"/simple/{PACKAGE}",
                    f"/extra/{PACKAGE}",
                    f"/secondary/simple/{PACKAGE}",
                }:
                    self.simple_response()
                    return
                if clean == "/flat":
                    self.simple_response()
                    return
                if self.path.startswith("/packages/"):
                    if self.wheel_response(pathlib.Path(self.path).name):
                        return
                self.send_response(404)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()

            do_GET = route
            do_HEAD = route

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def endpoint(self, path: str, token: str | None = None) -> str:
        if token is None:
            return f"http://127.0.0.1:{self.port}{path}"
        return f"http://aws:{token}@127.0.0.1:{self.port}{path}"


def run(transcript, env, uv, *args):
    transcript.write("$ uv " + " ".join(args) + "\n")
    proc = subprocess.run(
        [str(uv), *args],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    transcript.write(f"exit={proc.returncode}\n{proc.stdout}\n")
    transcript.flush()
    return proc


def scenario_env(root: pathlib.Path, name: str):
    scenario = root / name
    home = scenario / "home"
    config_home = scenario / "config"
    tool_dir = scenario / "tools"
    bin_dir = scenario / "bin"
    cache_dir = scenario / "cache"
    for directory in (home, config_home, tool_dir, bin_dir, cache_dir):
        directory.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(config_home),
        UV_TOOL_DIR=str(tool_dir),
        UV_TOOL_BIN_DIR=str(bin_dir),
        UV_CACHE_DIR=str(cache_dir),
        UV_NO_PROGRESS="1",
        UV_NO_CACHE="1",
        UV_PYTHON_DOWNLOADS="never",
    )
    return scenario, config_home / "uv" / "uv.toml", tool_dir, bin_dir, env


def write_config(path: pathlib.Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def public_version(bin_dir: pathlib.Path) -> str:
    proc = subprocess.run(
        [str(bin_dir / PACKAGE)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"public tool failed: {proc.stdout}")
    return proc.stdout.strip()


def receipt(tool_dir: pathlib.Path) -> str:
    return (tool_dir / PACKAGE / "uv-receipt.toml").read_text(encoding="utf-8")


def assert_upgrade(transcript, env, uv, bin_dir):
    upgraded = run(transcript, env, uv, "tool", "upgrade", PACKAGE)
    if upgraded.returncode != 0:
        raise RuntimeError("tool upgrade failed")
    version = public_version(bin_dir)
    transcript.write(f"public_after_upgrade={version}\n")
    if "0.2.0" not in version:
        raise RuntimeError(f"expected public 0.2.0, got: {version}")


def legacy_config_rotation(transcript, root, uv):
    transcript.write("===== legacy user-config credential rotation =====\n")
    _, config, tool_dir, bin_dir, env = scenario_env(root, "legacy-config")
    server = IndexServer(root / "legacy-config-index", authenticated=True)
    try:
        write_config(
            config,
            "\n".join(
                [
                    f'index-url = "{server.endpoint("/simple", OLD_TOKEN)}"',
                    f'extra-index-url = ["{server.endpoint("/extra", OLD_TOKEN)}"]',
                    f'find-links = ["{server.endpoint("/flat", OLD_TOKEN)}"]',
                    "",
                ]
            ),
        )
        installed = run(
            transcript,
            env,
            uv,
            "tool",
            "install",
            "--python",
            sys.executable,
            "--compile-bytecode",
            PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("legacy config install failed")
        installed_receipt = receipt(tool_dir)
        if f"127.0.0.1:{server.port}" in installed_receipt:
            raise RuntimeError("config-origin endpoint leaked into tool receipt")
        if "compile-bytecode = true" not in installed_receipt:
            raise RuntimeError("non-index receipt option was unexpectedly removed")
        if "0.1.0" not in public_version(bin_dir):
            raise RuntimeError("legacy config install did not publish 0.1.0")

        server.token = NEW_TOKEN
        server.versions = ["0.1.0", "0.2.0"]
        write_config(
            config,
            "\n".join(
                [
                    f'index-url = "{server.endpoint("/simple", NEW_TOKEN)}"',
                    f'extra-index-url = ["{server.endpoint("/extra", NEW_TOKEN)}"]',
                    f'find-links = ["{server.endpoint("/flat", NEW_TOKEN)}"]',
                    "",
                ]
            ),
        )
        request_start = len(server.requests)
        assert_upgrade(transcript, env, uv, bin_dir)
        rotated_requests = server.requests[request_start:]
        if not any(
            authorized and expected == "new" and presented == "new"
            for _, _, authorized, expected, presented in rotated_requests
        ):
            raise RuntimeError("upgrade never used refreshed user-config credentials")
        transcript.write("legacy_config_rotation=true\n")
    finally:
        server.close()


def legacy_cli_durable(transcript, root, uv):
    transcript.write("===== legacy CLI endpoint durability =====\n")
    _, config, tool_dir, bin_dir, env = scenario_env(root, "legacy-cli")
    server = IndexServer(root / "legacy-cli-index", authenticated=False)
    try:
        # Keep filesystem configuration absent. Every endpoint below is explicit CLI state.
        with contextlib.suppress(FileNotFoundError):
            config.unlink()
        simple = server.endpoint("/simple")
        extra = server.endpoint("/extra")
        flat = server.endpoint("/flat")
        installed = run(
            transcript,
            env,
            uv,
            "tool",
            "install",
            "--python",
            sys.executable,
            "--index-url",
            simple,
            "--extra-index-url",
            extra,
            "--find-links",
            flat,
            PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("legacy CLI install failed")
        installed_receipt = receipt(tool_dir)
        for endpoint in (simple, extra, flat):
            if endpoint not in installed_receipt:
                raise RuntimeError(f"explicit CLI endpoint was not persisted: {endpoint}")
        server.versions = ["0.1.0", "0.2.0"]
        assert_upgrade(transcript, env, uv, bin_dir)
        transcript.write("legacy_cli_durable=true\n")
    finally:
        server.close()


def modern_config_refresh(transcript, root, uv):
    transcript.write("===== modern user-config index refresh =====\n")
    _, config, tool_dir, bin_dir, env = scenario_env(root, "modern-config")
    server = IndexServer(root / "modern-config-index", authenticated=False)
    try:
        endpoint = server.endpoint("/simple")
        write_config(
            config,
            "\n".join(
                [
                    "[[index]]",
                    'name = "fieldwork"',
                    f'url = "{endpoint}"',
                    "default = true",
                    "",
                ]
            ),
        )
        installed = run(
            transcript,
            env,
            uv,
            "tool",
            "install",
            "--python",
            sys.executable,
            PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("modern config install failed")
        if endpoint in receipt(tool_dir):
            raise RuntimeError("modern config-origin index leaked into tool receipt")
        server.versions = ["0.1.0", "0.2.0"]
        assert_upgrade(transcript, env, uv, bin_dir)
        transcript.write("modern_config_refresh=true\n")
    finally:
        server.close()


def modern_cli_durable(transcript, root, uv):
    transcript.write("===== modern CLI default-index durability =====\n")
    _, config, tool_dir, bin_dir, env = scenario_env(root, "modern-cli")
    server = IndexServer(root / "modern-cli-index", authenticated=False)
    try:
        with contextlib.suppress(FileNotFoundError):
            config.unlink()
        endpoint = server.endpoint("/simple")
        installed = run(
            transcript,
            env,
            uv,
            "tool",
            "install",
            "--python",
            sys.executable,
            "--default-index",
            endpoint,
            PACKAGE,
        )
        if installed.returncode != 0:
            raise RuntimeError("modern CLI install failed")
        if endpoint not in receipt(tool_dir):
            raise RuntimeError("modern CLI default index was not persisted")
        server.versions = ["0.1.0", "0.2.0"]
        assert_upgrade(transcript, env, uv, bin_dir)
        transcript.write("modern_cli_durable=true\n")
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
        legacy_cli_durable(transcript, args.root, args.uv)
        modern_config_refresh(transcript, args.root, args.uv)
        modern_cli_durable(transcript, args.root, args.uv)
        transcript.write(
            "VALIDATED: config-origin endpoints are rediscovered and explicit CLI endpoints remain durable\n"
        )
        transcript.flush()


if __name__ == "__main__":
    main()
