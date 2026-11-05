"""Alfabeto portugues (PT-PT) aceito nas transcricoes."""
import unicodedata

LOWER = "abcdefghijklmnopqrstuvwxyz"
ACCENTED = "áàâãçéêíóôõúü"
PUNCT = ".-'"   # abreviaturas (Fr.co), nomes compostos, apostrofo

ALLOWED = set(LOWER + LOWER.upper() + ACCENTED + ACCENTED.upper() + PUNCT)


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def validate(text: str) -> str | None:
    """Devolve mensagem de erro, ou None se a transcricao e valida."""
    if not text:
        return "Transcrição vazia."
    if any(c.isspace() for c in text):
        return "Use uma palavra por retângulo."
    bad = sorted({c for c in text if c not in ALLOWED})
    if bad:
        return f"Caracteres fora do alfabeto PT: {' '.join(bad)}"
    return None
