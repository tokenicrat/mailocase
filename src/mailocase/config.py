from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "editor": "nano",
    "addresses": [],
    "default_from": "",
    "list_address": "list@example.com",
    "encode_emails": False,
    "site": {
        "title": "Mailocase Archive",
        "footer": "Powered by Mailocase",
        "homepage_text": "",
        "favicon": "",
        "sort_order": "oldest_first",
    },
}


def find_config() -> Path | None:
    """Walk up from cwd to find config.json."""
    current = Path.cwd()
    while True:
        candidate = current / "config.json"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = find_config()
    if path is None:
        raise FileNotFoundError("config.json not found. Run 'mailocase init' first.")
    with path.open() as f:
        data = json.load(f)
    cfg: dict[str, Any] = DEFAULT_CONFIG.copy()
    cfg.update(data)
    cfg["site"] = {**DEFAULT_CONFIG["site"], **data.get("site", {})}
    return cfg


def save_config(cfg: dict[str, Any], path: Path) -> None:
    with path.open("w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def _extract_email(addr_str: str) -> str:
    """Extract bare email from 'Name <email>' or 'email' string."""
    m = re.search(r"<([^>]+)>", addr_str)
    return m.group(1).strip() if m else addr_str.strip()


def lookup_user(addr_str: str, addresses: list[dict]) -> dict | None:
    """Match by email or 'name <email>'. Name-only not allowed. Returns user dict or None."""
    email = _extract_email(addr_str).lower()
    for d in addresses:
        if d.get("email", "").lower() == email:
            return d
    return None


def format_address(user: dict) -> str:
    """Return 'Name <email>' if name present, else 'email'."""
    name = user.get("name", "").strip()
    email = user.get("email", "")
    return f"{name} <{email}>" if name else email
