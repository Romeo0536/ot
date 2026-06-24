"""โหลดและเก็บค่า config จาก config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml


@dataclass
class Config:
    provider: str
    model: str
    inbox: Path
    organized: Path
    ledger: Path
    categories: List[str]
    default_currency: str

    @classmethod
    def load(cls, config_path: str | Path = "config.yaml") -> "Config":
        config_path = Path(config_path)
        base = config_path.parent
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        paths = data["paths"]
        return cls(
            provider=data.get("provider", "gemini"),
            model=data.get("model", "gemini-2.5-flash"),
            inbox=base / paths["inbox"],
            organized=base / paths["organized"],
            ledger=base / paths["ledger"],
            categories=data["categories"],
            default_currency=data.get("default_currency", "THB"),
        )
