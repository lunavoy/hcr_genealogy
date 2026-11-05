"""Gera os splits de treinamento a partir de labels.csv."""
import argparse
import csv
import math
import random

from .. import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-ratio", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    if not config.LABELS_CSV.exists():
        raise SystemExit(
            f"{config.LABELS_CSV} ainda nao existe. "
            "Coloque imagens em dataset/originals, inicie o servidor, "
            "confirme as transcricoes humanas e tente novamente."
        )

    with open(config.LABELS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("labels.csv vazio. Confirme palavras na interface primeiro.")

    rng = random.Random(a.seed)
    sources = sorted({r["source_image"] for r in rows})
    if len(sources) >= 5:
        # separa por pagina inteira: evita a mesma letra/pagina em treino e validacao
        rng.shuffle(sources)
        val_src = set(sources[:max(1, math.ceil(a.val_ratio * len(sources)))])
        is_val = lambda r: r["source_image"] in val_src
    else:
        is_val = lambda r: rng.random() < a.val_ratio

    train = [r for r in rows if not is_val(r)]
    val = [r for r in rows if is_val(r)]
    config.DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    for name, part in (("train", train), ("val", val)):
        with open(config.DATASETS_DIR / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["crop_file", "text"])
            w.writeheader()
            w.writerows({"crop_file": r["crop_file"], "text": r["text"]} for r in part)
    print(f"train: {len(train)} | val: {len(val)} | paginas: {len(sources)}")


if __name__ == "__main__":
    main()
