"""Validate the optional Compose profile, optionally start it and probe its health.

Run from any directory: python3 backend/scripts/check_vexa.py --help.
Only the Vexa services are started; no real meeting is joined and no key is printed.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ("vexa", "vexa-postgres", "vexa-whisper")


def validate(config: dict) -> None:
    services = config["services"]
    internal = {name for name, network in config["networks"].items() if network.get("internal")}
    for name in SERVICES:
        service = services[name]
        if "vexa" not in service.get("profiles", []):
            raise ValueError(f"{name}: missing optional vexa profile")
        if not re.fullmatch(r"[^@]+:[^@]+@sha256:[0-9a-f]{64}", service["image"]):
            raise ValueError(f"{name}: image must be pinned by tag and digest")
        if service.get("ports"):
            raise ValueError(f"{name}: host ports must not be published")
        if not internal.intersection(service["networks"]):
            raise ValueError(f"{name}: internal network required")
        if not service.get("healthcheck", {}).get("test"):
            raise ValueError(f"{name}: healthcheck required")
        for volume in service.get("volumes", []):
            if "docker.sock" in volume.get("source", ""):
                raise ValueError(f"{name}: Docker socket mount is forbidden")
    if set(services["vexa-postgres"]["networks"]) - internal:
        raise ValueError("Vexa database must have no egress network")
    for name in ("vexa", "vexa-whisper"):
        if not set(services[name]["networks"]) - internal:
            raise ValueError(f"{name}: outbound network required for Meet/model downloads")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--project", default="baraza")
    parser.add_argument("--gpu", action="store_true", help="Validate the Linux/NVIDIA override")
    parser.add_argument("--start", action="store_true", help="Start Vexa and verify health")
    parser.add_argument("--timeout", type=int, default=300, help="Health wait timeout in seconds")
    args = parser.parse_args()
    env_file = args.env_file.resolve()
    environment = {**os.environ, "BARAZA_ENV_FILE": str(env_file)}
    command = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-p",
        args.project,
        "-f",
        str(ROOT / "docker-compose.yml"),
    ]
    if args.gpu:
        command += ["-f", str(ROOT / "docker-compose.vexa-gpu.yml")]
    command += ["--profile", "vexa"]

    def run(arguments: list[str], timeout: int = 60) -> str:
        # Compose config contains credentials. Keep its output and failure text private.
        result = subprocess.run(
            command + arguments,
            env=environment,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("Docker Compose command failed; inspect the local service status")
        return result.stdout

    try:
        validate(json.loads(run(["config", "--format", "json"])))
        print("PASS: optional profile, pinned images, healthchecks and network isolation")
        if args.start:
            if shutil.disk_usage(ROOT).free < 15 * 1024**3:
                raise RuntimeError("At least 15 GiB of free host disk space is required")
            run(
                ["up", "-d", "--wait", "--wait-timeout", str(args.timeout), "vexa"],
                timeout=args.timeout + 1800,
            )
            probe = (
                "import urllib.request; "
                "[urllib.request.urlopen('http://localhost:'+str(p)+'/health',timeout=10)"
                " for p in (8056,8001,8080,8090)]; "
                "urllib.request.urlopen('http://vexa-whisper:8000/health',timeout=10)"
            )
            run(["exec", "-T", "vexa", "python3", "-c", probe])
            print("PASS: Vexa gateway, admin, meeting API, runtime and Whisper health endpoints")
        return 0
    except RuntimeError as error:
        print(f"FAIL: {error}; no runtime validation claimed", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {type(error).__name__}; no runtime validation claimed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
