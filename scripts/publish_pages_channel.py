#!/usr/bin/env python3
"""Publish built conda packages to the GitHub Pages conda channel.

The ``gh-pages`` branch of this repository is a static conda channel:

    https://<owner>.github.io/<repo>/linux-64/repodata.json

The ``.conda`` files themselves are too large for git (100 MB limit), so
they live as GitHub Release assets and the repodata ``urls`` point at the
release asset download URLs (object-storage direct links, 2 GB cap per
asset). Consumers do:

    conda config --add channels https://<owner>.github.io/<repo>
    conda install ninfer          # deps resolve from conda-forge

Package entry metadata (name/version/build/depends/...) is taken from the
rattler-build output repodata.json in ``output/linux-64/``; this script
adds the download URLs, merges with the channel's current repodata (read
from the gh-pages branch via the GitHub contents API — no Pages/CDN lag),
and pushes the result back to gh-pages. Before pushing, entries whose
download URL no longer exists on any live GitHub Release are pruned
(self-healing sync: when CI deletes an old per-build release, its channel
entry disappears on the next publish).

Usage (inside CI):
    python3 scripts/publish_pages_channel.py --mode release --tag 0.1.0
    python3 scripts/publish_pages_channel.py --mode nightly
    python3 scripts/publish_pages_channel.py --mode release --tag 0.1.0 \
        --rehash /path/to/asset.conda --dry-run

Environment:
    GH_TOKEN or GITHUB_TOKEN   token with ``contents: write``
    GITHUB_REPOSITORY          owner/repo (optional, defaults to the feedstock)
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO_DEFAULT = "sunnyyangyangyang/ninfer-feedstock"
NIGHTLY_TAG = "nightly"
GIT_AUTHOR = "pages-channel bot <pages-channel@ninfer-feedstock.local>"


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def gh_api(token, method, path, body=None):
    """Minimal GitHub REST call; returns parsed JSON or an error dict."""
    url = f"https://api.github.com/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ninfer-pages-channel-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return {"__status__": e.code, "body": e.read().decode(errors="replace")[:400]}
    except Exception as e:  # network errors
        return {"__status__": -1, "body": repr(e)}


def fetch_current_repodata(token, owner, name):
    data = gh_api(
        token, "GET",
        f"repos/{owner}/{name}/contents/linux-64/repodata.json?ref=gh-pages",
    )
    if isinstance(data, dict) and "content" in data:
        try:
            current = json.loads(base64.b64decode(data["content"]))
            current.setdefault("packages.conda", {})
            return current
        except Exception as e:
            print(f"warning: could not parse current repodata: {e!r}; starting fresh")
    return {
        "info": {"subdir": "linux-64"},
        "packages": {},
        "packages.conda": {},
        "repodata_version": 2,
    }


def collect_new_entries(outdir, owner, name, tag, rehash_file=None):
    """Entries for the files built in this run, from rattler's repodata."""
    rep_path = os.path.join(outdir, "repodata.json")
    if not os.path.exists(rep_path):
        die(f"rattler repodata not found at {rep_path}")
    with open(rep_path) as f:
        rattler = json.load(f)
    base_url = f"https://github.com/{owner}/{name}/releases/download/{tag}"
    entries = {}
    for fname, meta in (rattler.get("packages.conda") or {}).items():
        path = os.path.join(outdir, fname)
        if not os.path.exists(path):
            continue
        meta = dict(meta)
        if rehash_file:
            with open(rehash_file, "rb") as fb:
                blob = fb.read()
            meta["sha256"] = hashlib.sha256(blob).hexdigest()
            meta["md5"] = hashlib.md5(blob, usedforsecurity=False).hexdigest()
            meta["size"] = len(blob)
            print(f"rehashed {fname} from {rehash_file} (sha256={meta['sha256'][:12]}...)")
        download_url = f"{base_url}/{fname}"
        meta["urls"] = [download_url]
        # libmamba (mamba/micromamba, incl. upstream main as of 2.4.0) reads
        # the SINGULAR "url" key and silently ignores the standard "urls"
        # list; without it mamba re-derives <channel>/<subdir>/<filename>
        # and 404s (package files live on Release assets, not on Pages).
        # Classic conda (rudder) reads "urls" and ignores the extra key.
        meta["url"] = download_url
        entries[fname] = meta
    if not entries:
        die(f"no package entries found in {rep_path} with existing .conda files")
    return entries


def live_release_urls(token, owner, name):
    """Set of download URLs of every asset on every live release."""
    urls = set()
    page = 1
    while True:
        data = gh_api(
            token, "GET",
            f"repos/{owner}/{name}/releases?per_page=100&page={page}",
        )
        if not isinstance(data, list):
            die(f"could not list releases: {data!r}")
        for rel in data:
            for a in rel.get("assets", []):
                u = a.get("browser_download_url")
                if u:
                    urls.add(u)
        if len(data) < 100:
            break
        page += 1
    return urls


def prune_dead_entries(pc, live):
    """Drop entries whose URL no longer exists on any live release."""
    dead = [
        k for k, v in pc.items()
        if v.get("url") not in live
        and not any(u in live for u in (v.get("urls") or []))
    ]
    for k in dead:
        print(f"pruning dead entry: {k} (no matching live release asset)")
        del pc[k]
    return dead


def push_to_ghpages(token, owner, name, repodata, dry_run):
    """Commit linux-64/repodata.json (+ mirror + index.html) to gh-pages."""
    work = "/tmp/pages-channel-work"
    subprocess.run(["rm", "-rf", work], check=True)
    os.makedirs(os.path.join(work, "linux-64"))
    os.makedirs(os.path.join(work, "noarch"))
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    git = lambda *a: subprocess.run(
        ["git", "-C", work, *a], env=env, capture_output=True, text=True)

    git("init", "-q")
    git("remote", "add", "origin",
        f"https://x-access-token:{token}@github.com/{owner}/{name}.git")
    f = git("fetch", "--depth", "1", "origin", "gh-pages")
    branch_exists = f.returncode == 0
    if branch_exists:
        git("checkout", "-q", "-B", "gh-pages", "FETCH_HEAD")
    else:
        git("checkout", "-q", "--orphan", "gh-pages")
        print("gh-pages branch does not exist yet; creating it")

    payload = json.dumps(repodata, separators=(",", ":"), sort_keys=False)
    for fn in ("repodata.json", "current_repodata.json"):
        with open(os.path.join(work, "linux-64", fn), "w") as fh:
            fh.write(payload)
    # some clients hard-fail on a 404 for noarch/repodata.json; serve an
    # empty noarch subdir so the channel is unconditionally complete
    noarch = {
        "info": {"subdir": "noarch"},
        "packages": {},
        "packages.conda": {},
        "repodata_version": 2,
    }
    npayload = json.dumps(noarch, separators=(",", ":"))
    for fn in ("repodata.json", "current_repodata.json"):
        with open(os.path.join(work, "noarch", fn), "w") as fh:
            fh.write(npayload)
    with open(os.path.join(work, "index.html"), "w") as fh:
        fh.write(
            "<!doctype html>\n<meta charset=\"utf-8\">\n"
            f"<title>NInfer conda channel ({owner}/{name})</title>\n"
            "<h1>NInfer conda channel &mdash; GitHub Pages</h1>\n"
            "<p>Static conda channel for NInfer (RTX 5090 / sm_120a builds). "
            "Package files are hosted as GitHub Release assets.</p>\n"
            "<pre>conda config --add channels "
            f"https://{owner}.github.io/{name}\nconda install ninfer</pre>\n"
            '<p>Current metadata: <a href="linux-64/repodata.json">linux-64/repodata.json</a></p>\n'
        )

    if dry_run:
        print(f"[dry-run] would push {len(repodata.get('packages.conda', {}))} "
              f"package(s) to gh-pages; skipping push")
        return

    git("add", "-A")
    st = git("diff", "--cached", "--quiet")
    if st.returncode == 0:
        print("gh-pages content unchanged; nothing to push")
        return
    c = git("-c", f"user.name={GIT_AUTHOR.split(' ')[0]}",
            "-c", f"user.email={GIT_AUTHOR.split(' ')[1][1:-1]}",
            "commit", "-q", "-m",
            f"publish channel: {len(repodata.get('packages.conda', {}))} package(s)")
    if c.returncode != 0:
        die(f"git commit failed: {c.stderr}")
    p = git("push", "origin", "gh-pages")
    if p.returncode != 0:
        die(f"git push failed: {p.stderr}")
    print(f"pushed gh-pages: https://{owner}.github.io/{name}/linux-64/repodata.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", required=True, choices=["release", "nightly"])
    ap.add_argument("--tag", help="release tag (mode=release)")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", REPO_DEFAULT))
    ap.add_argument("--outdir", default="output/linux-64")
    ap.add_argument("--rehash", metavar="FILE",
                    help="recompute sha256/md5/size from this file (local seeding "
                         "from the CI-built release asset)")
    ap.add_argument("--dry-run", action="store_true",
                    help="do everything except the final push")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        die("missing GH_TOKEN / GITHUB_TOKEN")
    if "/" not in args.repo:
        die(f"bad --repo {args.repo!r}")
    owner, name = args.repo.split("/", 1)
    tag = args.tag if args.mode == "release" else NIGHTLY_TAG
    if args.mode == "release" and not tag:
        die("mode=release requires --tag")

    # 1) entries for the files built in this run
    new_entries = collect_new_entries(args.outdir, owner, name, tag, args.rehash)
    print(f"new entries: {sorted(new_entries)}")

    # 2) current channel repodata
    current = fetch_current_repodata(token, owner, name)
    pc = current["packages.conda"]
    pc.update(new_entries)

    # 3) drop entries whose release no longer exists (pruned by CI, or the
    #    retired rolling `nightly` release); keeps channel == releases
    if not args.dry_run:
        live = live_release_urls(token, owner, name)
        prune_dead_entries(pc, live)

    # 4) normalize the document shape conda expects
    out = {
        "info": {"subdir": "linux-64"},
        "packages": {},
        "packages.conda": pc,
        "repodata_version": 2,
    }
    print(f"channel now has {len(pc)} package(s): "
          + ", ".join(sorted(pc)))

    # 5) push
    push_to_ghpages(token, owner, name, out, args.dry_run)


if __name__ == "__main__":
    main()
