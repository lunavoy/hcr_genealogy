"""Persistencia dos registros e das caixas de palavras detectadas."""
from __future__ import annotations

import json
import threading
from datetime import datetime

from . import config

_lock = threading.Lock()


def _read() -> list[dict]:
    path = config.CONFIRMED_DIR / "records.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(records: list[dict]) -> None:
    config.CONFIRMED_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.CONFIRMED_DIR / "records.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def create(source: str, box: dict, lines: list[dict], words: list[dict]) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    record_id = f"{source}|{box['x']}|{box['y']}|{box['w']}|{box['h']}"
    record = {
        "id": record_id, "source_image": source, "box": box,
        "created_at": now, "updated_at": now, "status": "pending",
        "lines": lines, "words": words,
    }
    with _lock:
        records = [r for r in _read() if r["id"] != record_id]
        records.append(record)
        _write(records)
    return record


def save(record: dict) -> dict:
    """Persiste explicitamente um rascunho sem alterar outros registros."""
    with _lock:
        records = _read()
        now = datetime.now().isoformat(timespec="seconds")
        record["updated_at"] = now
        layout_path = config.CONFIRMED_DIR / "layout_training.jsonl"
        config.CONFIRMED_DIR.mkdir(parents=True, exist_ok=True)
        with open(layout_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "source_image": record["source_image"],
                "record_box": record["box"],
                "lines": record.get("lines", []),
            }, ensure_ascii=False) + "\n")
        for i, current in enumerate(records):
            if current["id"] == record["id"]:
                records[i] = record
                _write(records)
                return record
        record.setdefault("created_at", now)
        records.append(record)
        _write(records)
        return record


def get(record_id: str) -> dict | None:
    return next((r for r in _read() if r["id"] == record_id), None)


def update(record_id: str, record: dict) -> dict:
    with _lock:
        records = _read()
        for i, current in enumerate(records):
            if current["id"] == record_id:
                record["updated_at"] = datetime.now().isoformat(timespec="seconds")
                records[i] = record
                _write(records)
                return record
    raise KeyError("Registro não encontrado.")


def all_for(source: str | None) -> list[dict]:
    return [r for r in _read() if source is None or r["source_image"] == source]
