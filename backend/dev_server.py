"""
Local dev entrypoint for the backend.

Use an import string so uvicorn can enable file watching when requested.
Reload is disabled by default for a stable local process tree.
"""

from __future__ import annotations

import os

import uvicorn


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    reload = _env_flag("BACKEND_RELOAD", default=False)

    os.environ["BACKEND_HOST"] = host
    os.environ["BACKEND_PORT"] = str(port)
    os.environ["BACKEND_RELOAD_MODE"] = "enabled" if reload else "disabled"
    uvicorn.run("main:app", host=host, port=port, reload=reload)
