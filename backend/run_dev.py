from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

import uvicorn


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the PoltAIshow backend API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8879, type=int)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_config = uvicorn.config.LOGGING_CONFIG.copy()
    log_config["handlers"] = {
        **log_config.get("handlers", {}),
        "file": {
            "class": "logging.FileHandler",
            "formatter": "default",
            "filename": str(log_dir / "backend-uvicorn.log"),
            "encoding": "utf-8",
        },
    }
    log_config["loggers"] = {
        **log_config.get("loggers", {}),
        "uvicorn": {"handlers": ["default", "file"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default", "file"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access", "file"], "level": "INFO", "propagate": False},
    }
    logging.captureWarnings(True)
    sys.path.insert(0, str(project_root))
    from backend.app.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=False,
        app_dir=str(project_root),
        log_config=log_config,
    )
