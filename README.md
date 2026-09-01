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

- Each 12-hour build publishes its own tag + GitHub Release:
  `v<YYYY.MM.DD.HHMM>-<githash7>` (asset
  `ninfer-<YYYY.MM.DD.HHMM>-<githash7>-sm120a_h<hash>_0`, `_h<hash>_0` is
  rattler-build's content fingerprint). The newest 3 per-build releases are
  retained, older ones (release + tag) are deleted, so a plain
  `conda install ninfer` always picks the newest timestamp while release
  storage stays bounded (~1.4 GB).
- Builds are dispatched at 00:00/12:00 UTC on the minute by a maintainer
  host's systemd timer (GitHub's free-tier `schedule` cron was observed
  lagging 2.5–3.7 h; see `scripts/ci-timer/`), so the newest build is
  typically available ~15 min past the top of the even UTC hour.
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

### Installing with mamba/micromamba: direct release-asset URL

mamba (and micromamba) can install a `.conda` file by direct URL — the
exact file the channel references, minus the (broken) channel
indirection:

```bash
# 1. current asset names, straight from the channel repodata
#    (…or just open https://github.com/sunnyyangyangyang/ninfer-feedstock/releases):
curl -s https://sunnyyangyangyang.github.io/ninfer-feedstock/linux-64/repodata.json \
    | python3 -c 'import json,sys; [print(k) for k in sorted(json.load(sys.stdin)["packages.conda"], reverse=True)]'

# 2. install. Run deps (cuda-cudart 13.*, ffmpeg, libcurl, libstdcxx-ng)
#    must be satisfiable from the prefix or your channels (add `-c conda-forge`).
#    <tag> is the per-build release tag (v<YYYY.MM.DD.HHMM>-<githash7>);
#    the repodata entry's "url" field is the exact asset URL to paste:
mamba install -p <prefix> \
    "https://github.com/sunnyyangyangyang/ninfer-feedstock/releases/download/<tag>/<asset>.conda"
```

Until libmamba stops discarding per-package repodata URLs, or the binaries
are hosted at `<channel>/<subdir>/<file>` on size-unlimited object storage,
this direct-URL form is the only mamba-side path. Classic `conda` needs no
such workaround.

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

Output: `output/linux-64/ninfer-0.1.0-*.conda`

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
  Bump `version` + `source url/sha256` together for updates.

## Verifying the built package

```bash
mamba create -n ninfer-test -c conda-forge \
    -f output/linux-64/ninfer-*.conda -y
mamba run -n ninfer-test ninfer-serve --help
```
