"""Mede CER e acerto de palavra no split de validação."""
import csv

import jiwer
from PIL import Image

from .. import config
from ..recognizer import Recognizer


def main():
    with open(config.DATASETS_DIR / "val.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("val.csv vazio.")
    rec = Recognizer()
    refs, hyps = [], []
    for r in rows:
        img = Image.open(config.CROPS_DIR / r["crop_file"])
        c = rec.predict(img)
        refs.append(r["text"]); hyps.append(c[0]["text"] if c else "")
    cer = jiwer.cer(refs, hyps)
    wacc = sum(a == b for a, b in zip(refs, hyps)) / len(refs)
    print(f"Modelo: {rec.source}\nAmostras: {len(rows)}\nCER: {cer:.3%}\nPalavras exatas: {wacc:.1%}")


if __name__ == "__main__":
    main()
