# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""A stand-in for the ``lakelet`` executable for the shell's tests. ``init <folder>`` writes a
``lakelet.toml`` the way core step 2 does and prints what it created; ``-C <project> serve``
takes the real arguments, records them, writes ``.lakelet/serve.json`` the way core step 9
does, prints the ``serving`` line, then lives for LAKELET_FAKE_LIFETIME seconds (0: refuse
and exit)."""

import json
import os
import secrets
import sys
import time

args = sys.argv[1:]

if args and args[0] == "init":
    folder = args[1]
    if os.path.exists(os.path.join(folder, "lakelet.toml")):
        print(f"{folder} is already a Lakelet project", file=sys.stderr)
        sys.exit(1)
    # `--warehouse s3://bucket/prefix` (decisions W1), refused for anything else, as the core does
    warehouse = args[args.index("--warehouse") + 1] if "--warehouse" in args else "./warehouse"
    if warehouse != "./warehouse" and not warehouse.startswith("s3://"):
        print(f"the warehouse is ./warehouse or an s3://bucket/prefix, not {warehouse}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.join(folder, ".lakelet"), exist_ok=True)
    with open(os.path.join(folder, "lakelet.toml"), "w", encoding="utf-8") as f:
        f.write(f'[project]\nname = "{os.path.basename(folder.rstrip(os.sep))}"\nwarehouse = "{warehouse}"\n')
    print("  lakelet.toml\n  .lakelet/")
    if warehouse != "./warehouse":
        print(f"  every table's files go to {warehouse} (the catalog stays in .lakelet/)")
    sys.exit(0)

if args[:2] == ["bucket", "check"]:
    # decisions P1: the core's check, answered by the prefix's name — a bucket called
    # `denied-…` refuses the write, `nokeys-…` has no credentials, anything not s3:// is bad
    prefix = args[2]
    profile = os.environ.get("AWS_PROFILE")
    source = "none" if prefix.startswith("s3://nokeys-") else "profile" if profile else "environment"
    creds = {"configured": source != "none", "source": source, "profile": profile, "region": "us-east-1", "endpoint": None}
    if not prefix.startswith("s3://") or "/" not in prefix[5:]:
        result = {"prefix": prefix, "credentials": creds, "read": False, "write": False, "error": "a warehouse is an s3://bucket/prefix"}
    elif prefix.startswith("s3://denied-") or source == "none":
        result = {"prefix": prefix, "credentials": creds, "read": True, "write": False, "error": "ACCESS_DENIED during PutObject operation"}
    else:
        result = {"prefix": prefix, "credentials": creds, "read": True, "write": True, "error": None}
    result["ok"] = result["read"] and result["write"]
    where = "keys from the environment" if source == "environment" else "no credentials in the environment"
    result["sentence"] = f"{prefix} is writable with {where}; one object was written and removed." if result["ok"] else f"{prefix}: {result['error']} ({where})."
    if "--json" in args:
        print(json.dumps(result))
    else:
        print(result["sentence"])
    sys.exit(0 if result["ok"] else 1)

project = args[args.index("-C") + 1]
lifetime = int(os.environ.get("LAKELET_FAKE_LIFETIME", "60"))
lakelet_dir = os.path.join(project, ".lakelet")
os.makedirs(lakelet_dir, exist_ok=True)
with open(os.path.join(lakelet_dir, "fake-args.txt"), "w", encoding="utf-8") as f:
    f.write(" ".join(args))
    if "LAKELET_DEV_ORIGIN" in os.environ:
        f.write(f" env LAKELET_DEV_ORIGIN={os.environ['LAKELET_DEV_ORIGIN']}")
    if "AWS_PROFILE" in os.environ:
        f.write(f" env AWS_PROFILE={os.environ['AWS_PROFILE']}")
    f.write(f" cwd={os.getcwd()}")

if lifetime == 0:
    print("fake sidecar refusing to start", file=sys.stderr)
    sys.exit(1)

port = 40000 + (os.getpid() % 10000)
with open(os.path.join(lakelet_dir, "serve.json"), "w", encoding="utf-8") as f:
    json.dump({"port": port, "pid": os.getpid(), "token": secrets.token_urlsafe(32), "started": "now"}, f)
print(f"serving http://127.0.0.1:{port}: /api (bearer token in serve.json) and /v1 (the catalog)")
print("Ctrl-C stops it.")
sys.stdout.flush()
time.sleep(lifetime)
