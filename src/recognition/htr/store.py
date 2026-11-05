"""Persistencia das confirmacoes: recortes, labels.csv e lexico."""
from __future__ import annotations

import csv
import hashlib
import json
import threading
from datetime import datetime

from . import config

FIELDS = ["id", "crop_file", "text", "predicted", "confidence", "was_correct",
          "source_image", "x", "y", "w", "h", "timestamp"]
_lock = threading.Lock()


def _read_rows() -> list[dict]:
    if not config.LABELS_CSV.exists():
        return []
    with open(config.LABELS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_rows(rows: list[dict]) -> None:
    config.CONFIRMED_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.LABELS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


def _write_lexicon(rows: list[dict]) -> None:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["text"]] = counts.get(r["text"], 0) + 1
    with open(config.LEXICON_JSON, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(counts.items())), f, ensure_ascii=False, indent=1)


def load_lexicon() -> dict[str, int]:
    if not config.LEXICON_JSON.exists():
        return {}
    with open(config.LEXICON_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_confirmation(*, source: str, box, crop, text: str,
                      predicted: str = "", confidence: float = 0.0) -> dict:
    """Salva (ou corrige) a transcricao de um retangulo. Mesmo retangulo = mesma linha."""
    x, y, w, h = box
    uid = hashlib.sha1(f"{source}|{x}|{y}|{w}|{h}".encode()).hexdigest()[:12]
    with _lock:
        config.CROPS_DIR.mkdir(parents=True, exist_ok=True)
        crop.save(config.CROPS_DIR / f"{uid}.png")
        row = {"id": uid, "crop_file": f"{uid}.png", "text": text, "predicted": predicted,
               "confidence": f"{confidence:.4f}", "was_correct": int(predicted == text),
               "source_image": source, "x": x, "y": y, "w": w, "h": h,
               "timestamp": datetime.now().isoformat(timespec="seconds")}
        rows = [r for r in _read_rows() if r["id"] != uid] + [row]
        _write_rows(rows)
        _write_lexicon(rows)
    return row


def delete_confirmation(*, source: str, box) -> None:
    """Remove a confirmação e o recorte associados a um retângulo."""
    x, y, w, h = box
    uid = hashlib.sha1(f"{source}|{x}|{y}|{w}|{h}".encode()).hexdigest()[:12]
    with _lock:
        rows = _read_rows()
        kept = [r for r in rows if r["id"] != uid]
        if len(kept) == len(rows):
            return
        _write_rows(kept)
        _write_lexicon(kept)
        (config.CROPS_DIR / f"{uid}.png").unlink(missing_ok=True)


def boxes_for(source: str) -> list[dict]:
    return [{k: int(r[k]) for k in ("x", "y", "w", "h")}
            for r in _read_rows() if r["source_image"] == source]

