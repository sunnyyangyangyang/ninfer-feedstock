# ninfer-feedstock

conda-forge-style feedstock for [NInfer](https://github.com/Neroued/ninfer),
a high-performance local LLM inference framework that targets a single
NVIDIA GeForce RTX 5090 (`sm_120a`, Blackwell, CUDA 13.x).

Built with [rattler-build](https://rattler.build/).

## What the package contains

| Item | Location | Notes |
| --- | --- | --- |
| `ninfer` | `$PREFIX/bin/ninfer` | interactive / one-shot CLI |
| `ninfer-serve` | `$PREFIX/bin/ninfer-serve` | HTTP server, OpenAI/Anthropic-compatible API |
| `ninfer-perplexity` | `$PREFIX/bin/ninfer-perplexity` | perplexity benchmark app |
| public C++ API | `$PREFIX/include/ninfer/*.h` | `engine.h`, `types.h`, … |

The upstream project defines no CMake `install()` rules, so `build.sh`
mirrors the upstream Dockerfile and copies the app binaries and public
headers manually.

## Installing from the channel

This feedstock publishes its own conda channel as a static GitHub Pages
site: `linux-64/repodata.json` lives on the `gh-pages` branch, while the
~440 MB `.conda` files themselves are GitHub Release assets referenced by
the repodata `urls` (they exceed git's 100 MB file limit, not the release
asset cap).

```bash
conda config --add channels https://sunnyyangyangyang.github.io/ninfer-feedstock
conda install ninfer            # run deps (cuda-cudart 13.x, ffmpeg, libcurl)
                                # resolve automatically from conda-forge
```

- Each 12-hour run fetches the **latest NInfer commit** (default-branch
  HEAD of `Neroued/ninfer`) and publishes it under its own tag + GitHub
  Release: `v<YYYY.MM.DD.HHMM>-<hash7>` (asset
  `ninfer-<YYYY.MM.DD.HHMM>-<hash7>.conda` — the recipe's static
  `build.string` is exactly `<hash7>` (no arch suffix in the package
  identity — the package hard-rejects every GPU but the RTX 5090 anyway),
  so the filename and the package's `build` field carry no opaque
  fingerprint tail). `<hash7>` is
  the first seven chars of the upstream commit the package was built from
  — not this feedstock repo's commit hash (issue #1). Every release also
  ships a twin asset under the constant name `ninfer-latest.conda` (same
  bytes), whose
  `releases/latest/download/ninfer-latest.conda` URL always resolves to
  the newest build — a stable *download* URL for scripts (mamba/micromamba
  users install the per-tag real-name URL instead; see the mamba section
  below). If upstream
  has no new commit since the previous successful run **and** the recipe is
  unchanged, the run **skips** without publishing: the channel already
  carries the latest code, so a rebuild would only produce duplicate
  assets. (The skip check compares both inputs recorded in the newest
  release's notes — the upstream commit *and* the feedstock commit — so a
  recipe change such as a cherry-picked patch forces a rebuild at the next
  run. A caveat of tracking only the default-branch HEAD: an upstream
  commit that is not on any branch yet is invisible to the run — that is
  what recipe patches below are for.) The newest 3 per-build
  releases are retained, older ones (release + tag) are deleted, so a
  plain `conda install ninfer` always picks the newest timestamp while
  release storage stays bounded (~1.4 GB).
- The `source:` pin in `recipe/meta.yaml` is the **stable baseline**:
  versioned releases (`build-and-release.yml`) and local
  `rattler build` use it as written. The continuous workflow re-pins it
  in its own CI checkout per run, so the pin in the repo never drifts.
- `recipe/meta.yaml` may carry `source: patches:` — upstream commits
  cherry-picked on top of the source pin while they are not (yet) on any
  upstream branch (a loose commit object is invisible to the continuous
  build's `git ls-remote HEAD`, so without the patch it could sit
  unshipped for days: 2026-09-05, commit `d8e2a27a` — vision envelope
  262144 tokens — committed on top of `ad0f3d38`, on no branch). Every
  run applies the patch on top of the upstream HEAD it fetches and lists
  it in the release notes. When the fetched HEAD becomes the patch's own
  commit sha, the workflow drops the patch lines automatically; at that
  point bump the `source:` pin on main to that sha and delete the patch
  file (patches are `git format-patch`-style `a/`/`b/` diffs, applied
  with `patch -p1` by both builders).
- ⚠️ The channel tracks upstream HEAD: while upstream is in a broken
  in-flight state, the newest channel entry may fail to build or misbehave
  until upstream fixes it. Install a slightly older timestamped build
  instead (pin `ninfer=<ts>`, or use the direct-URL form below).
- Builds are dispatched at 00:00/12:00 UTC by an external cron service
  that fires GitHub's `workflow_dispatch` API on schedule (GitHub's
  free-tier `schedule` cron was observed lagging 2.5–3.7 h, and the
  maintainer's machine is not 24/7 — see `scripts/ci-cron/`), so the
  newest build is typically available ~15 min past the top of the even
  UTC hour.
- Runtime requires the system NVIDIA driver (`libcuda.so.1`) and a
  GeForce RTX 5090 — the project hard-rejects every other CUDA
  architecture (`sm_120a` only). Model weights are not included.

## Client compatibility: the mamba/micromamba caveat

The channel layout is **metadata on Pages, binaries on GitHub Releases**:
`repodata.json` (small) lives on the Pages site, while the ~440–460 MB
`.conda` files live as Release assets and are referenced from repodata via
the standard `urls` field (plus the singular `url` key, which libmamba
parses). Whether the plain `config --add channels … && install ninfer` flow
works depends on the client:

| Client | channel flow | Why |
| --- | --- | --- |
| classic conda | ✅ works | conda honors the repodata `urls` list and downloads from the release-asset URLs |
| mamba / micromamba (libmamba 2.x, incl. upstream `main`) | ❌ 404 | libmamba's solver layer overwrites **every** package URL with `<channel>/<subdir>/<filename>` (`set_solvables_url()` in `libmamba/src/solver/libsolv/helpers.cpp`), discarding the repodata-advertised URLs before the download. The file cannot instead live on the Pages site: it exceeds git's 100 MB file limit, and GitHub Pages does not resolve Git LFS pointers (it would serve the ~130-byte pointer text instead of the package — [community discussion #104092](https://github.com/orgs/community/discussions/104092)) |

The `Failed to load subdir … repodata.json.zst … 404` warnings during
`mamba install` are harmless: the channel publishes plain `repodata.json`
and libmamba transparently falls back to it.

### Installing / updating with mamba/micromamba: per-tag direct URL

mamba (and micromamba) can install a `.conda` file by direct URL — the
exact file the channel references, minus the (broken) channel
indirection. One catch: libmamba derives name/version/build **from the
filename** (right-to-left on `-`, three segments required), so the URL
has to point at the **real asset name** `ninfer-<ts>-<hash7>.conda` —
the two-segment `ninfer-latest.conda` alias is rejected with `Missing
name in filename`. Each release's tag is exactly its asset directory, so
any per-tag URL is stable forever:

```bash
# install, or replace-update the installed build, in one command —
# swap the tag for a newer one to jump builds (same package name, newer
# version: the solver unlinks the old one automatically).
# <ts> = the build's YYYY.MM.DD.HHMM stamp, <hash7> = the upstream NInfer
# commit it was built from (releases page, or the repodata name list in
# the next section):
mamba install \
    "https://github.com/sunnyyangyangyang/ninfer-feedstock/releases/download/v<ts>-<hash7>/ninfer-<ts>-<hash7>.conda"
```

Verified working (latest build at time of writing):

```bash
mamba install \
    "https://github.com/sunnyyangyangyang/ninfer-feedstock/releases/download/v2026.09.05.1924-ad0f3d3/ninfer-2026.09.05.1924-ad0f3d3.conda"
```

The `ninfer-latest.conda` twin asset (identical bytes, constant name)
stays as the stable **download** URL for automation — GitHub's
`/releases/latest/download/ninfer-latest.conda` always serves the newest
build. To `mamba install` that file locally, download it under its real
asset name first (e.g. `curl -O` the alias URL, then rename to
`ninfer-<ts>-<hash7>.conda`): libmamba parses the filename, so installing
the two-segment alias name would misreport the package identity.

Run deps (cuda-cudart 13.*, ffmpeg, libcurl, libstdcxx-ng) must be
satisfiable from the prefix or your channels (add `-c conda-forge`).

### Pinning a specific build (direct release-asset URL)

`<tag>` is the per-build release tag (`v<YYYY.MM.DD.HHMM>-<hash7>`,
upstream NInfer commit hash); the repodata entry's "url" field is the
exact asset URL to paste (…or open
<https://github.com/sunnyyangyangyang/ninfer-feedstock/releases>):

```bash
# 1. current asset names, straight from the channel repodata:
curl -s https://sunnyyangyangyang.github.io/ninfer-feedstock/linux-64/repodata.json \
    | python3 -c 'import json,sys; [print(k) for k in sorted(json.load(sys.stdin)["packages.conda"], reverse=True)]'

# 2. install that specific build:
mamba install -p <prefix> \
    "https://github.com/sunnyyangyangyang/ninfer-feedstock/releases/download/<tag>/<asset>.conda"
```

### Gotchas (mamba + local files)

- **Relative paths need `./` or an absolute path.** `mamba install
  Downloads/foo.conda` (no `./`) is parsed as *channel `Downloads`* and
  libmamba then 404s on `conda.anaconda.org/Downloads/foo.conda`.
- **The `ninfer-latest.conda` alias name is only two dash-segments.**
  libmamba's filename parser (name/version/build from the filename,
  right-to-left) requires three segments, so both URL and local-file
  installs of the alias fail with `Missing name in filename`. Use the
  per-tag real-name URL above, or download the alias under its real
  asset name first.
- Installing from a **local file** (not a channel) prints
  `Could not validate package …: md5 and sha256 sum unknown` — harmless:
  there is no repodata to verify against. `--no-safety-checks` silences
  it.
- Until libmamba stops discarding per-package repodata URLs, or the
  binaries are hosted at `<channel>/<subdir>/<file>` on size-unlimited
  object storage, these URL/file forms are the only mamba-side paths.
  Classic `conda` needs no such workaround.

## The recipe: one file, two builders

`recipe/meta.yaml` is written in the **intersection of the conda-build and
rattler-build v0.75 recipe schemas** — deliberately jinja-free plain YAML:

| Constraint | Reason |
| --- | --- |
| no `{% %}` / `{{ }}` jinja, no `# [selectors]` | rattler-build v0.75 parses recipe files as raw YAML (no jinja pass) |
| no top-level `skip:` | `skip` is not in rattler's strict recipe schema → the platform guard (linux-64 only) lives at the top of `build.sh` |
| literal `gcc`/`gxx` instead of `{{ compiler(...) }}` | the macro is jinja; the compiler meta packages are the macro's output anyway |
| `about: homepage:` (not `home:`) | rattler's `about` schema only knows `homepage`; conda-build accepts both |
| `tests:` section in the recipe + `run_test.sh` on disk | rattler runs the `tests:` section; conda-build ignores that key and runs `run_test.sh` — same `--help` smoke test either way |
| static `build: string:` (no jinja, no `--build-string-prefix`) | both builders accept a static build string; rattler-build uses it **verbatim** (no auto `_h<hash>_0` content-fingerprint tail), conda-build appends the build number (`_0`) — cosmetic difference only |
| `source: patches:` with `git format-patch`-style `a/`/`b/` diffs | both builders apply source patches with `patch -p1`; keep new patches in that format so the shared file stays builder-neutral |

So the same feedstock builds under:

- `rattler build -r recipe/meta.yaml -c conda-forge` (note: the **file**,
  rattler's directory mode only looks for `recipe.yaml`), and
- standard conda-forge / conda-smithery CI (conda-build, which renders the
  jinja-free file unchanged).

If you ever upstream to conda-forge and its linter complains about
`homepage:` vs `home:`, or you want the idiomatic `skip: true
# [not linux64]` line back, split the recipe again — but for this channel
the shared file keeps a single source of truth.

## Dependency mapping (from the upstream mamba env)

The upstream local build uses a mamba prefix created with:

```
mamba create -p .deps --override-channels -c conda-forge \
    cmake>=3.28 ninja gxx_linux-64 pkgconf ffmpeg libcurl>=7.85 cuda-toolkit=13.*
```

The feedstock maps that 1:1:

| mamba env spec | feedstock section | recipe dep |
| --- | --- | --- |
| `gxx_linux-64` (pulls gcc/cxx) | build | `gxx`, `gcc` (upstream env resolved gxx 15.3, the newest at the time) |
| `cmake>=3.28` | build | `cmake >=3.28` |
| `ninja` | build | `ninja` |
| `pkgconf` | build | `pkgconf` |
| `cuda-toolkit=13.*` | host | `cuda-toolkit 13.*` |
| `ffmpeg` | host + run | `ffmpeg` (libavformat/libavcodec/libavutil/libswscale via pkg-config) |
| `libcurl>=7.85` | host + run | `libcurl` (host pins `>=7.85`) |
| — (runtime, from `ldd`) | run | `cuda-cudart 13.*`, `libstdcxx-ng` |

`ldd` on the built binaries shows exactly one CUDA tool library
(`libcudart.so.13`); `libcuda.so.1` is provided by the system NVIDIA driver
and is deliberately not a conda dependency. The runtime CUDA requirement is
therefore only `cuda-cudart`, while the full `cuda-toolkit` is needed at
build time for `nvcc` and the CMake `CUDAToolkit` config.

## Building

```bash
# rattler keeps its package/repodata cache under XDG_CACHE_HOME; point it
# somewhere writable if ~/.cache is not:
export XDG_CACHE_HOME="$HOME/.cache"   # or any writable dir

rattler build \
    -r recipe/meta.yaml \
    -c conda-forge
```

Output: `output/linux-64/ninfer-0.1.0-*.conda` (the baseline pin on
main — identity rides on the `<commit7>` build string, not the
version number; continuous CI builds are timestamped instead)

### Notes

- **Platform**: `linux-64` only. The project hard-rejects every CUDA
  architecture except `sm_120a`, which only exists on GeForce RTX 5090;
  `build.sh` refuses any other target platform.
- **GPU not needed to build**: `nvcc` cross-compiles on the CPU; the
  smoke test (`--help`) also exits before any CUDA initialization, so
  GPU-less CI machines are fine. Actually *running* inference requires a
  physical RTX 5090 plus a model artifact, e.g.
  `hf download neroued/Qwen3.8-27B-NInfer qwen3_8_27b.ninfer --local-dir models`.
- **NVTX3 quirk**: the project includes `<nvtx3/nvToolsExt.h>`, but conda's
  CUDA prefix does not expose the nvtx3 headers on the CMake CUDAToolkit
  include path — they ship inside the `nsight-compute` package. The
  upstream local mamba prefix has a manual symlink for this, and `build.sh`
  replicates it on the build prefix
  (`targets/x86_64-linux/include/nvtx3 -> <nsight-compute>/.../nvtx/include/nvtx3`).
- **Versioning**: upstream has no tags or in-tree version, so the package
  version is pinned to an upstream commit (see `source:` in `meta.yaml`).
  Bump `version` + `source url/sha256` + `build.string` (+ `source
  patches`, if any) together for updates (the build string is
  `<commit7>` — no arch suffix — see `build:` in `meta.yaml`). Cherry-picked
  upstream commits that are not on any upstream branch yet go into
  `source: patches:` instead of a pin bump (see the "Recipe patches"
  bullet above) — that is how `d8e2a27a` ships since 2026-09-05. Per-build release tags (`v<ts>-<hash7>`) and asset names
  carry the hash of the upstream commit that build was made from
  (continuous builds pull upstream HEAD per run; versioned builds use the
  pinned baseline) — not this feedstock repo's hash — so a tag always
  identifies the exact NInfer source the package was built from.

## Verifying the built package

```bash
mamba create -n ninfer-test -c conda-forge \
    -f output/linux-64/ninfer-*.conda -y
mamba run -n ninfer-test ninfer-serve --help
```
