"""Loading of config/*.yaml."""

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


def load(name: str) -> dict:
    with open(CONFIG / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def file_hash(name: str) -> str:
    return hashlib.sha256((CONFIG / f"{name}.yaml").read_bytes()).hexdigest()[:12]
