import json
import os
import sys

import probe_dep


def main() -> None:
    print(json.dumps({
        "marker": probe_dep.MARKER,
        "module": probe_dep.__file__,
        "executable": sys.executable,
        "prefix": sys.prefix,
        "cwd": os.getcwd(),
        "pythonpath": os.environ.get("PYTHONPATH"),
        "sys_path": sys.path,
    }, indent=2))
