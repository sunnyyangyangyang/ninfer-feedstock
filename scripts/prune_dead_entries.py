#!/usr/bin/env python3
"""One-shot: prune channel entries whose releases no longer exist.

Run after deleting the retired rolling `nightly` release (phase-2
migration). Reuses the publish script's fetch/prune/push machinery.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location(
    "ppc", os.path.join(HERE, "publish_pages_channel.py"))
ppc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ppc)

token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
if not token:
    ppc.die("missing GH_TOKEN / GITHUB_TOKEN")
owner, name = "sunnyyangyangyang", "ninfer-feedstock"

current = ppc.fetch_current_repodata(token, owner, name)
pc = current["packages.conda"]
print(f"channel entries before: {sorted(pc)}")
live = ppc.live_release_urls(token, owner, name)
dead = ppc.prune_dead_entries(pc, live)
if not dead:
    print("nothing to prune; channel already in sync")
    sys.exit(0)

out = {
    "info": {"subdir": "linux-64"},
    "packages": {},
    "packages.conda": pc,
    "repodata_version": 2,
}
print(f"channel entries after:  {sorted(pc)}")
if "--dry-run" in sys.argv:
    print("[dry-run] skipping push")
    sys.exit(0)
ppc.push_to_ghpages(token, owner, name, out, dry_run=False)
print("done")
