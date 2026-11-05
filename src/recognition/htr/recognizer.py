"""Motor de reconhecimento (TrOCR). Isolado aqui: trocar de motor = reescrever so este arquivo."""
from __future__ import annotations

import math

from . import config


class Recognizer:
    def __init__(self):
        self._model = None
        self._processor = None
        self.source = None

    def _load(self):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        if (config.CURRENT_MODEL / "config.json").exists():
            path, kw = str(config.CURRENT_MODEL), {}
        else:
            path, kw = config.BASE_MODEL, {"cache_dir": str(config.BASE_CACHE)}
        self._processor = TrOCRProcessor.from_pretrained(path, **kw)
        self._model = VisionEncoderDecoderModel.from_pretrained(path, **kw)
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(self._device).eval()
        self.source = path

    def reload(self):
        self._model = None

    def predict(self, image, lexicon: dict[str, int] | None = None) -> list[dict]:
        """Devolve candidatos [{text, confidence, in_lexicon}] do melhor para o pior.

        confidence = media geometrica da probabilidade dos tokens (0-1).
        E uma estimativa NAO calibrada; calibre com o conjunto de validacao depois.
        """
        import torch

        if self._model is None:
            self._load()
        lexicon = lexicon or {}
        pv = self._processor(images=image.convert("RGB"), return_tensors="pt").pixel_values.to(self._device)
        n = config.NUM_BEAMS
        with torch.no_grad():
            out = self._model.generate(pv, num_beams=n, num_return_sequences=n,
                                       max_new_tokens=config.MAX_LABEL_LEN,
                                       output_scores=True, return_dict_in_generate=True)
        texts = self._processor.batch_decode(out.sequences, skip_special_tokens=True)
        scores = out.sequences_scores.tolist()

        seen, cands = set(), []
        for t, s in zip(texts, scores):
            t = t.strip()
            if not t or t in seen:
                continue
            seen.add(t)
            cands.append({"text": t, "confidence": round(math.exp(s), 4),
                          "in_lexicon": t in lexicon})
        # palavras ja confirmadas antes ganham uma ajuda no ranking (nao na confianca exibida)
        cands.sort(key=lambda c: c["confidence"] *
                   (1 + config.LEXICON_BONUS * math.log1p(lexicon.get(c["text"], 0))), reverse=True)
        return cands
