#!/usr/bin/env bash
# Builds NInfer with CMake + Ninja inside the conda build prefix.
# Mirrors the upstream local build (mamba prefix .deps) and the upstream
# Dockerfile: Ninja generator, Release, sm_120a only, apps on, tests and
# benchmarks off.
set -euo pipefail

# Platform guard: NInfer only supports linux-64 (CMAKE_CUDA_ARCHITECTURES=120a
# exists only on the RTX 5090). A jinja-free shared recipe cannot use
# conda-build's `skip:` key without breaking rattler-build's strict recipe
# schema, so the guard lives here. (rattler-build does not set CONDA_TARGET,
# hence the uname fallback for native builds.)
case "${CONDA_TARGET:-linux-$(uname -m)}" in
  linux-64|linux-x86_64) ;;
  *)
    echo "Error: ninfer only builds for linux-64 (sm_120a, RTX 5090)." >&2
    echo "       Refusing to build for target '${CONDA_TARGET:-$(uname -m)}'." >&2
    exit 1
    ;;
esac

# Fall back to the conda prefix C++ compiler if the activation did not
# export CXX (rattler-build's strict isolation mode).
: "${CXX:=${PREFIX}/bin/x86_64-conda-linux-gnu-g++}"

# NVTX3 header exposure. The project's src/core/nvtx.h includes
# <nvtx3/nvToolsExt.h>, but conda's CUDA prefix never puts the nvtx3 headers
# on the CMake CUDAToolkit include path (targets/x86_64-linux/include); they
# ship inside the nsight-compute package. The upstream local build worked
# around this with a manual symlink in its mamba prefix, which we replicate
# here on the build prefix:
#   targets/x86_64-linux/include/nvtx3 -> <nsight-compute>/.../nvtx/include/nvtx3
NVTX3_SRC="$(find "$PREFIX" -type d -path "*/nvtx/include/nvtx3" 2>/dev/null | head -1)"
if [ -z "$NVTX3_SRC" ]; then
  echo "Error: nvtx3 headers not found under $PREFIX" >&2
  echo "       (expected from the nsight-compute package of the CUDA toolkit)." >&2
  exit 1
fi
mkdir -p "${PREFIX}/targets/x86_64-linux/include"
ln -sfn "$NVTX3_SRC" "${PREFIX}/targets/x86_64-linux/include/nvtx3"

cmake -S "${SRC_DIR}" -B "${BUILD_DIR}" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_ARCHITECTURES=120a \
    -DCMAKE_CUDA_COMPILER="${PREFIX}/bin/nvcc" \
    -DCMAKE_CUDA_HOST_COMPILER="${CXX}" \
    -DNINFER_BUILD_APPS=ON \
    -DBUILD_TESTING=OFF \
    -DNINFER_BUILD_BENCHMARKS=OFF

# Upstream AGENTS.md: use unrestricted build-tool parallelism, i.e.
# `cmake --build <dir> -j` without a numeric job limit.
cmake --build "${BUILD_DIR}" -j

# The upstream project defines no CMake install() rules, so installation
# mirrors the upstream Dockerfile: ship the app binaries.
mkdir -p "${PREFIX}/bin"
cp "${BUILD_DIR}/apps/ninfer" "${PREFIX}/bin/"
cp "${BUILD_DIR}/apps/ninfer-serve" "${PREFIX}/bin/"
cp "${BUILD_DIR}/apps/ninfer-perplexity" "${PREFIX}/bin/"

# Public C++ API headers (include/ninfer/*.h) for downstream consumers.
# They use "ninfer/..."-style includes, so the source include/ tree is
# copied verbatim into $PREFIX/include.
mkdir -p "${PREFIX}/include"
cp -r "${SRC_DIR}/include/." "${PREFIX}/include/"
