from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


DEFAULT_BASE_URL = "https://0-0.pro/v1"


@dataclass
class AppConfig:
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = ""
    thordata_key: str = ""
    search_mode: bool = False

    @staticmethod
    def load(path: Path) -> "AppConfig":
        if not path.exists():
            return AppConfig()
        data = json.loads(path.read_text(encoding="utf-8"))
        base_url = str(data.get("BASE_URL", "")).strip()
        if not base_url:
            base_url = DEFAULT_BASE_URL
        return AppConfig(
            api_key=str(data.get("API_KEY", "")),
            base_url=base_url,
            model=str(data.get("MODEL", "")),
            thordata_key=str(data.get("THORDATA_KEY", "")),
            search_mode=bool(data.get("SEARCH_MODE", False)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "API_KEY": self.api_key,
            "BASE_URL": self.base_url,
            "MODEL": self.model,
            "THORDATA_KEY": self.thordata_key,
            "SEARCH_MODE": self.search_mode,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def masked_summary(self) -> str:
        def mask(value: str) -> str:
            value = value or ""
            if len(value) <= 8:
                return "*" * len(value)
            return f"{value[:4]}****{value[-4:]}"

        return (
            f"API_KEY={mask(self.api_key)}\n"
            f"BASE_URL={self.base_url}\n"
            f"MODEL={self.model}\n"
            f"网页抓取 Key（ThorData）={mask(self.thordata_key)}\n"
            f"搜索模式（无需网页抓取Key）={'开启' if self.search_mode else '关闭'}"
        )
