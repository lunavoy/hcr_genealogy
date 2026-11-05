"""Conversão de PageXML do eScriptorium para registros editáveis."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

Point = list[int]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _points(value: str | None) -> list[Point]:
    if not value:
        return []
    result: list[Point] = []
    for pair in value.split():
        try:
            x, y = pair.split(",", 1)
            result.append([int(round(float(x))), int(round(float(y)))])
        except ValueError as exc:
            raise ValueError(f"Coordenada PageXML inválida: {pair!r}") from exc
    return result


def _children(element: ET.Element, name: str) -> Iterable[ET.Element]:
    return (child for child in element.iter() if _local_name(child.tag) == name)


def _text(element: ET.Element) -> str:
    for child in _children(element, "Unicode"):
        return child.text or ""
    return ""


def _polygon_box(points: list[Point]) -> dict[str, int]:
    if len(points) < 3:
        raise ValueError("Um polígono precisa de pelo menos três pontos.")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {"x": min(xs), "y": min(ys),
            "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


def _region_record(region: ET.Element, image_name: str, index: int) -> dict:
    region_points: list[Point] = []
    for coords in _children(region, "Coords"):
        region_points = _points(coords.get("points"))
        break
    region_box = _polygon_box(region_points)
    lines: list[dict] = []
    words: list[dict] = []

    for line_index, line in enumerate(_children(region, "TextLine"), 1):
        line_points: list[Point] = []
        for coords in _children(line, "Coords"):
            line_points = _points(coords.get("points"))
            break
        if len(line_points) < 3:
            continue
        lines.append({
            "id": line.get("id") or f"line-{index:04d}-{line_index:04d}",
            "points": line_points,
            "baseline": next(
                (_points(coords.get("points"))
                 for coords in _children(line, "Baseline")),
                [],
            ),
            "text": _text(line),
        })
        for word_index, word in enumerate(_children(line, "Word"), 1):
            word_points: list[Point] = []
            for coords in _children(word, "Coords"):
                word_points = _points(coords.get("points"))
                break
            if len(word_points) < 3:
                continue
            words.append({
                "id": word.get("id") or (
                    f"word-{index:04d}-{line_index:04d}-{word_index:04d}"),
                "line": line_index - 1,
                "points": word_points,
                "box": _polygon_box(word_points),
                "text": _text(word),
                "predicted": "",
                "confidence": 0,
                "candidates": [],
                "status": "reviewed" if _text(word) else "pending",
            })

    return {
        "id": region.get("id") or f"region-{index:04d}",
        "source_image": image_name,
        "box": region_box,
        "polygon": region_points,
        "created_at": None,
        "updated_at": None,
        "status": "reviewed" if words and all(
            word["status"] == "reviewed" for word in words) else "pending",
        "group_id": "",
        "lines": lines,
        "words": words,
        "source_format": "PageXML",
    }


def load_pagexml(path: Path, image_name: str | None = None) -> list[dict]:
    """Lê regiões, linhas, baselines, palavras e transcrições de um PageXML."""
    if not path.is_file():
        raise FileNotFoundError(f"PageXML não encontrado: {path}")
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"PageXML inválido: {path}") from exc
    name = image_name or path.stem
    regions = list(_children(root, "TextRegion"))
    return [_region_record(region, name, index)
            for index, region in enumerate(regions, 1)]


def write_json(pathxml: Path, output: Path, image_name: str | None = None) -> None:
    records = load_pagexml(pathxml, image_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte PageXML do eScriptorium em registros JSON.")
    parser.add_argument("pagexml", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image-name")
    args = parser.parse_args()
    write_json(args.pagexml, args.output, args.image_name)


if __name__ == "__main__":
    main()
