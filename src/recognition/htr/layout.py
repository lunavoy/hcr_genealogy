"""Deteccao automatica de linhas e palavras dentro de um registro."""
from __future__ import annotations

import cv2
import numpy as np

from . import imaging


def _boxes(mask: np.ndarray, min_area: int) -> list[tuple[int, int, int, int]]:
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    return [
        tuple(int(v) for v in stats[i, :4])
        for i in range(1, n)
        if stats[i, cv2.CC_STAT_AREA] >= min_area
    ]


def _horizontal_points(x: int, y: int, w: int, h: int) -> list[list[int]]:
    """Representa cada linha com quatro nós e preferência horizontal."""
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def detect(img: np.ndarray, record_box: imaging.Box) -> dict:
    """Detecta linhas e agrupa a tinta em palavras usando OpenCV.

    O resultado e deliberadamente editavel: documentos historicos podem exigir
    que o usuario mova, divida ou remova caixas antes da revisao.
    """
    x, y, w, h = imaging.clamp_box(record_box, img.shape)
    mask = imaging.ink_mask(img[y:y + h, x:x + w], min_area=3)
    if not mask.any():
        return {"lines": [], "words": []}

    line_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(15, min(80, w // 18)), 3))
    line_mask = cv2.dilate(mask, line_kernel)
    lines = sorted(_boxes(line_mask, max(20, w // 500)), key=lambda b: b[1])
    detected_lines = []
    words = []
    for line_no, (lx, ly, lw, lh) in enumerate(lines):
        y0, y1 = y + ly, y + ly + lh
        detected_lines.append({
            "id": f"line-{line_no + 1:04d}",
            "points": _horizontal_points(x + lx, y0, lw, y1 - y0),
        })
        line = mask[max(0, ly - 2):min(h, ly + lh + 2),
                    max(0, lx - 2):min(w, lx + lw + 2)]
        word_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(5, min(28, w // 100)), 3))
        grouped = cv2.dilate(line, word_kernel)
        for wx, wy, ww, wh in sorted(_boxes(grouped, max(8, w // 2000)),
                                      key=lambda b: b[0]):
            if ww < 3 or wh < 3:
                continue
            words.append({
                "line": line_no,
                "box": {
                    "x": x + max(0, lx - 2) + wx,
                    "y": y + max(0, ly - 2) + wy,
                    "w": ww,
                    "h": wh,
                },
            })
    return {"lines": detected_lines, "words": words}


def words_for_lines(img: np.ndarray, lines: list[dict]) -> list[dict]:
    """Reagrupa palavras usando os polígonos de linhas corrigidos pelo usuário."""
    mask = imaging.ink_mask(img, min_area=3)
    result = []
    for line_no, line_data in enumerate(lines):
        points = np.array(line_data["points"], dtype=np.int32)
        x, y, w, h = cv2.boundingRect(points)
        roi = mask[y:y + h, x:x + w]
        polygon = points - (x, y)
        allowed = np.zeros_like(roi)
        cv2.fillPoly(allowed, [polygon], 255)
        roi = cv2.bitwise_and(roi, allowed)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(5, min(28, w // 100)), 3))
        grouped = cv2.dilate(roi, kernel)
        for wx, wy, ww, wh in sorted(_boxes(grouped, max(8, w // 2000)),
                                      key=lambda b: b[0]):
            if ww >= 3 and wh >= 3:
                result.append({"line": line_no, "box": {
                    "x": x + wx, "y": y + wy, "w": ww, "h": wh}})
    return result
