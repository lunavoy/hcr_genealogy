"""Operacoes de imagem: leitura, recorte e ajuste do retangulo a tinta."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

Box = tuple[int, int, int, int]  # x, y, largura, altura (pixels da imagem original)


def read_image(path) -> np.ndarray:
    # imdecode + fromfile funciona com acentos no caminho (Windows)
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Não foi possível abrir a imagem: {path}")
    return img


def clamp_box(box: Box, shape) -> Box:
    h_img, w_img = shape[:2]
    x, y, w, h = box
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w_img, x + w), min(h_img, y + h)
    if x1 - x0 < 1 or y1 - y0 < 1:
        raise ValueError("Retângulo fora da imagem ou vazio.")
    return (x0, y0, x1 - x0, y1 - y0)


def ink_mask(bgr: np.ndarray, min_area: int = 6, min_contrast: int = 25) -> np.ndarray:
    """Mascara binaria da tinta (255 = tinta). Vazia se nao houver contraste."""
    gray = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    thr, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ink, bg = gray[mask > 0], gray[mask == 0]
    if ink.size == 0 or bg.size == 0 or (bg.mean() - ink.mean()) < min_contrast:
        return np.zeros_like(mask)
    # remove ruido de papel (manchas minusculas)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == i] = 255
    return keep


def snap_to_ink(img: np.ndarray, box: Box, pad: int = 0) -> Box:
    """Encolhe o retangulo ate encostar na tinta. Sem tinta -> devolve o original."""
    x, y, w, h = clamp_box(box, img.shape)
    mask = ink_mask(img[y:y + h, x:x + w])
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return (x, y, w, h)
    x0, x1 = max(0, xs.min() - pad), min(w - 1, xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(h - 1, ys.max() + pad)
    return (x + int(x0), y + int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1))


def crop_pil(img: np.ndarray, box: Box) -> Image.Image:
    x, y, w, h = clamp_box(box, img.shape)
    return Image.fromarray(cv2.cvtColor(img[y:y + h, x:x + w], cv2.COLOR_BGR2RGB))
