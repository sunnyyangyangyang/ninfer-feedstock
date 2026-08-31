#!/usr/bin/env bash
# Smoke test. `--help` exits before any CUDA initialization (same call the
# upstream Dockerfile uses as its smoke test), so this passes on GPU-less
# CI runners. Real inference requires a physical RTX 5090 (sm_120a).
set -euo pipefail

"${PREFIX}/bin/ninfer" --help
"${PREFIX}/bin/ninfer-serve" --help
