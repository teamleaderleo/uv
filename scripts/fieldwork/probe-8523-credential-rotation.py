#!/usr/bin/env python3
import argparse
import base64
import hashlib
import http.server
import os
import pathlib
import subprocess
import sys
import threading
import zipfile

PACKAGE = "fieldwork-demo-tool"
MODULE = "fieldwork_demo_tool"


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
    record = "".join(f"{name},,\n" for name in files) + f"{record_path},,\n"
    files[record_path] = record.encode()
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return wheel_path


def run(transcript, env, uv, *args):
    command = [str(uv), *args]
    transcript.write("$ " + " ".join(args) + "\n")
    proc = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    transcript.write(f"exit={proc.returncode}\n{proc.stdout}\n")
    transcript.flush()
    return proc


def write_config(path: pathlib.Path, port: int, token: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'index-url = "http://aws:{token}@127.0.0.1:{port}/simple"\n',
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", required=True, type=pathlib.Path)
    parser.add_argument("--root", required=True, type=pathlib.Path)
    args = parser.parse_args()

    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    transcript_path = root / "transcript.txt"
    package_dir = root / "index"
    wheels = {
        "0.1.0": build_wheel(package_dir, "0.1.0"),
        "0.2.0": build_wheel(package_dir, "0.2.0"),
    }
    state = {"token": "old-token", "versions": ["0.1.0"]}
    request_log = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *values):
            return

        def authorized(self):
            expected = "Basic " + base64.b64encode(f"aws:{state['token']}".encode()).decode()
            authorized = self.headers.get("Authorization") == expected
            request_log.append((self.command, self.path, authorized, state["token"]))
            if not authorized:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="fieldwork"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return False
            return True

        def do_HEAD(self):
            if not self.authorized():
                return
            if self.path.startswith("/packages/"):
                filename = pathlib.Path(self.path).name
                for version in state["versions"]:
                    wheel = wheels[version]
                    if wheel.name == filename:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(wheel.stat().st_size))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        return
            self.send_response(404)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def do_GET(self):
            if not self.authorized():
                return

            if self.path.rstrip("/") == f"/simple/{PACKAGE}":
                body = "<html><body>" + "".join(
                    f'<a href="/packages/{wheels[version].name}">{wheels[version].name}</a>\n'
                    for version in state["versions"]
                ) + "</body></html>"
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return

            if self.path.startswith("/packages/"):
                filename = pathlib.Path(self.path).name
                for version in state["versions"]:
                    wheel = wheels[version]
                    if wheel.name == filename:
                        data = wheel.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(data)
                        return

            self.send_response(404)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    home = root / "home"
    config_home = root / "config"
    config = config_home / "uv" / "uv.toml"
    tool_dir = root / "tools"
    bin_dir = root / "bin"
    cache_dir = root / "cache"
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

    try:
        with transcript_path.open("w", encoding="utf-8") as transcript:
            transcript.write(f"uv={args.uv}\nindex=http://127.0.0.1:{port}/simple\n")
            write_config(config, port, "old-token")
            transcript.write("phase=install credential-generation=old version=0.1.0\n")
            install = run(
                transcript,
                env,
                args.uv,
                "tool",
                "install",
                "--python",
                sys.executable,
                PACKAGE,
            )
            if install.returncode != 0:
                raise SystemExit("initial tool install failed")

            receipt = tool_dir / PACKAGE / "uv-receipt.toml"
            receipt_before = receipt.read_text(encoding="utf-8")
            transcript.write("receipt_after_install_sha256=" + hashlib.sha256(receipt_before.encode()).hexdigest() + "\n")
            transcript.write(f"receipt_contains_endpoint={f'127.0.0.1:{port}' in receipt_before}\n")
            transcript.write(f"receipt_contains_credentials={'old-token' in receipt_before}\n")
            if f"127.0.0.1:{port}" not in receipt_before:
                raise SystemExit("receipt did not persist configured index endpoint")
            if "old-token" in receipt_before:
                raise SystemExit("receipt unexpectedly persisted short-lived credentials")

            public = bin_dir / PACKAGE
            first = subprocess.run([str(public)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            transcript.write(f"public_after_install={first.stdout.strip()}\n")
            if first.returncode != 0 or "0.1.0" not in first.stdout:
                raise SystemExit("installed public tool is not version 0.1.0")

            state["token"] = "new-token"
            state["versions"] = ["0.1.0", "0.2.0"]
            write_config(config, port, "new-token")
            transcript.write("phase=upgrade credential-generation=new versions=0.1.0,0.2.0\n")
            upgrade = run(transcript, env, args.uv, "tool", "upgrade", PACKAGE)

            for method, path, authorized, token_phase in request_log:
                phase = "new" if token_phase == "new-token" else "old"
                transcript.write(f"request method={method} path={path} authorized={authorized} expected_generation={phase}\n")
            transcript.flush()

            if upgrade.returncode != 0:
                transcript.write("RESULT=REPRODUCED: current uv failed after user-config credential rotation\n")
                raise SystemExit(2)

            second = subprocess.run([str(public)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            transcript.write(f"public_after_upgrade={second.stdout.strip()}\n")
            if second.returncode != 0 or "0.2.0" not in second.stdout:
                raise SystemExit("upgrade succeeded but public tool did not reach version 0.2.0")

            receipt_after = receipt.read_text(encoding="utf-8")
            transcript.write("receipt_after_upgrade_sha256=" + hashlib.sha256(receipt_after.encode()).hexdigest() + "\n")
            transcript.write(f"receipt_contains_rotated_credentials={'new-token' in receipt_after}\n")
            if "new-token" in receipt_after:
                raise SystemExit("upgraded receipt unexpectedly persisted rotated credentials")

            transcript.write("RESULT=NEGATIVE: current uv successfully followed rotated user-config credentials\n")
            transcript.flush()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
