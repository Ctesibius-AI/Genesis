# Genesis dev sandbox — an isolated Python 3.12 runtime.
#
# Purpose: build/run/test Genesis inside a container so nothing installs on the
# host Mac (which only has system Python 3.9; Genesis requires >=3.12).
#
# Lock-safety: this image contains ONLY a toolchain (uv + pytest). It never
# activates live capture and never deploys. Isolation is enforced at run time by
# compose.yaml (network:none, and ONLY the repo is mounted — never ~/.claude).
FROM python:3.12-slim

# uv for the toolchain/venv (installed from PyPI — no external image dependency).
# Keep byte-compilation and caches OFF the mounted host tree.
ENV PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache

# Dev toolchain lives in the image, not on the host: uv + a venv with pytest.
# Runtime deps are empty (Step 0 is stdlib-only), so nothing else is needed here.
RUN pip install --no-cache-dir uv \
 && uv venv "$VIRTUAL_ENV" --python 3.12 \
 && uv pip install "pytest>=8"

# Non-root user (uid 1000). Source is bind-mounted at run time and read from /workspace.
RUN useradd --create-home --uid 1000 genesis \
 && chown -R genesis:genesis "$VIRTUAL_ENV"
WORKDIR /workspace
USER genesis

# Keep the container available for `exec`/`run` shells. Overridden by `sandbox test`.
CMD ["sleep", "infinity"]
