"""Caminhos e parametros centrais. Altere aqui, nao espalhe pelo codigo."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[3]

# --- dados ---
DATASET_DIR = ROOT / "dataset"
RAW_DIR = DATASET_DIR / "originals"              # paginas originais
ANNOTATIONS_DIR = DATASET_DIR / "annotations"    # confirmacoes e metadados
CROPS_DIR = DATASET_DIR / "processed"            # recortes confirmados (PNG)
LABELS_CSV = ANNOTATIONS_DIR / "labels.csv"      # recorte -> transcricao
LEXICON_JSON = ANNOTATIONS_DIR / "lexicon.json"  # palavra -> quantas vezes confirmada
DATASETS_DIR = DATASET_DIR / "splits"            # train.csv / val.csv gerados
# Backwards-compatible name used by the persistence modules.
CONFIRMED_DIR = ANNOTATIONS_DIR

# --- modelos ---
MODELS_DIR = ROOT / "models" / "recognition"
BASE_CACHE = MODELS_DIR / "base"                 # download do modelo pre-treinado
FINETUNED_DIR = MODELS_DIR / "finetuned"
CURRENT_MODEL = FINETUNED_DIR / "current"        # o que o servidor usa, se existir
# TrOCR is not switched between languages by a runtime flag. This community
# checkpoint is fine-tuned for Portuguese; override it for a local model.
BASE_MODEL = os.environ.get(
    "HTR_BASE_MODEL", "mazafard/trocr-finetuned_20250422_125947")

# --- reconhecimento ---
NUM_BEAMS = 5            # quantas hipoteses o modelo devolve
MAX_LABEL_LEN = 32       # tokens maximos por palavra
LEXICON_BONUS = 0.15     # peso do "ja confirmei essa palavra antes" no ranking

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
