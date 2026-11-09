"""Runtime settings, read once from KCCS_* environment variables (12-factor style)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ...domain.temporal import parse_iso_utc


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("artifacts/api/kernel.sqlite")
    artifacts_dir: Path = Path("artifacts/api")
    data_dir: Path = Path("data")
    workbook: Path = Path("data/KCCS_Sentinel_Reference_Data_Pack.xlsx")
    autoload: bool = True
    demo_endpoints: bool = True
    fixed_now: datetime | None = None
    log_level: str = "INFO"
    log_format: str = "json"  # json | text
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ.get
        fixed = env("KCCS_FIXED_NOW")
        log_format = env("KCCS_LOG_FORMAT", "json").lower()
        if log_format not in {"json", "text"}:
            raise ValueError("KCCS_LOG_FORMAT must be 'json' or 'text'")
        return cls(
            db_path=Path(env("KCCS_DB_PATH", str(cls.db_path))),
            artifacts_dir=Path(env("KCCS_ARTIFACTS_DIR", str(cls.artifacts_dir))),
            data_dir=Path(env("KCCS_DATA_DIR", str(cls.data_dir))),
            workbook=Path(env("KCCS_WORKBOOK", str(cls.workbook))),
            autoload=_bool("KCCS_AUTOLOAD", cls.autoload),
            demo_endpoints=_bool("KCCS_DEMO_ENDPOINTS", cls.demo_endpoints),
            fixed_now=parse_iso_utc(fixed) if fixed else None,
            log_level=env("KCCS_LOG_LEVEL", cls.log_level).upper(),
            log_format=log_format,
            host=env("KCCS_HOST", cls.host),
            port=int(env("KCCS_PORT", str(cls.port))),
        )
