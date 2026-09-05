# ninfer-feedstock

[Conda channel](https://sunnyyangyangyang.github.io/ninfer-feedstock/) for
[NInfer](https://github.com/Neroued/ninfer) — a high-performance local LLM
inference framework for a single NVIDIA GeForce RTX 5090 (`sm_120a`,
Blackwell, CUDA 13.x). Packages are built with
[rattler-build](https://rattler.build/).

## What you get

| Item | Location | Purpose |
| --- | --- | --- |
| `ninfer` | `$PREFIX/bin/ninfer` | interactive / one-shot CLI |
| `ninfer-serve` | `$PREFIX/bin/ninfer-serve` | HTTP server, OpenAI/Anthropic-compatible API |
| `ninfer-perplexity` | `$PREFIX/bin/ninfer-perplexity` | perplexity benchmark |
| public C++ API | `$PREFIX/include/ninfer/` | `engine.h`, `types.h`, … |

**Requirements:** the system NVIDIA driver (`libcuda.so.1`) and a physical
RTX 5090 — the package hard-rejects every other GPU architecture. Model
weights are not included, e.g.
`hf download neroued/Qwen3.8-27B-NInfer qwen3_8_27b.ninfer --local-dir models`.

## Installing

The channel is refreshed every 12 hours and always tracks the newest
NInfer upstream commit. Each build is a GitHub Release tagged
`v<YYYY.MM.DD.HHMM>-<hash7>`, and its per-tag asset URL stays valid
forever — so any older build remains installable, which is also the
escape hatch when upstream is temporarily in a broken in-flight state
(just install a slightly older tag).

### mamba / micromamba

```bash
mamba install \
    "https://github.com/sunnyyangyangyang/ninfer-feedstock/releases/download/v2026.09.05.1924-ad0f3d3/ninfer-2026.09.05.1924-ad0f3d3.conda"
```

- **Update**: re-run the same command with a newer tag from the
  [releases page](https://github.com/sunnyyangyangyang/ninfer-feedstock/releases)
  (same package name, newer version — the old build is unlinked
  automatically).
- **Target an environment**: add `-p <prefix>`. Runtime deps (cuda-cudart
  13.x, ffmpeg, libcurl) resolve from conda-forge.
- **Why a direct URL instead of the channel?** libmamba discards the
  per-package URLs stored in the repodata, and the ~450 MB package is too
  large for the Pages site that hosts the channel metadata — the per-tag
  URL above is the reliable mamba-side path. The constant
  `.../releases/latest/download/ninfer-latest.conda` URL always serves the
  newest build and is handy for download-by-URL scripts; if you want to
  `mamba install` that file locally, save it under its real asset name
  first (the alias's two-part name is not parseable by libmamba).

### classic conda

```bash
conda config --add channels https://sunnyyangyangyang.github.io/ninfer-feedstock
conda install ninfer            # newest build; pin one with ninfer=<YYYY.MM.DD.HHMM>
```

## Maintainer notes

`recipe/meta.yaml` is jinja-free plain YAML accepted by both conda-build
and rattler-build; the constraint table and dependency mapping live in the
recipe's own comments. Local build:

```bash
rattler build -r recipe/meta.yaml -c conda-forge
```

CI runs twice daily (external cron → `workflow_dispatch`,
`scripts/ci-cron/`): it re-pins the recipe to the upstream HEAD, builds,
and publishes the per-tag GitHub Release plus this Pages channel; see
`.github/workflows/continuous-build.yml` for skip/prune semantics.
Cherry-picked upstream commits that are not on any branch yet ship via
`source: patches:` and are auto-dropped once upstream contains them
(`recipe/meta.yaml`).

Smoke-test a local build (no GPU needed):

```bash
mamba create -n ninfer-test -c conda-forge -f output/linux-64/ninfer-*.conda -y
mamba run -n ninfer-test ninfer-serve --help
```
