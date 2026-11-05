"""Servidor Flask mínimo: serve a página e endpoints da aplicação."""
from __future__ import annotations

import argparse
import functools
import io

import cv2
from flask import Flask, abort, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from . import charset, config, imaging, layout, records, store
from .recognizer import Recognizer

BROWSER_FORMATS = {".png", ".jpg", ".jpeg", ".webp"}


def create_app(use_model: bool = True) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    recognizer = Recognizer() if use_model else None

    def resolve(name: str):
        root = config.RAW_DIR.resolve()
        p = (root / name).resolve()
        if root not in p.parents or not p.is_file():
            abort(404)
        return p

    @functools.lru_cache(maxsize=4)
    def _load(path: str, mtime: float):
        return imaging.read_image(path)

    def get_image(name: str):
        p = resolve(name)
        return _load(str(p), p.stat().st_mtime)

    def get_box(data, img):
        b = data["box"]
        return imaging.clamp_box(tuple(int(round(float(b[k]))) for k in ("x", "y", "w", "h")), img.shape)

    def box_dict(box):
        return dict(zip(("x", "y", "w", "h"), box))

    @app.errorhandler(ValueError)
    @app.errorhandler(KeyError)
    def bad_request(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.description), e.code

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/images")
    def images():
        root = config.RAW_DIR.resolve()
        files = [p.relative_to(root).as_posix() for p in root.rglob("*")
                 if p.suffix.lower() in config.IMAGE_EXTS]
        return jsonify(sorted(files))

    @app.get("/api/image/<path:name>")
    def image(name):
        p = resolve(name)
        if p.suffix.lower() in BROWSER_FORMATS:
            return send_file(p)
        _, buf = cv2.imencode(".png", get_image(name))   # ex.: TIFF
        return send_file(io.BytesIO(buf.tobytes()), mimetype="image/png")

    @app.get("/api/confirmed")
    def confirmed():
        return jsonify(store.boxes_for(request.args["image"]))

    @app.post("/api/snap")
    def snap():
        d = request.get_json(force=True)
        img = get_image(d["image"])
        return jsonify(box_dict(imaging.snap_to_ink(img, get_box(d, img))))

    @app.get("/api/records")
    def list_records():
        return jsonify(records.all_for(request.args["image"]))

    @app.post("/api/records/analyze")
    def analyze_record():
        d = request.get_json(force=True)
        img = get_image(d["image"])
        record_box = get_box(d, img)
        detected = layout.detect(img, record_box)
        words = []
        for i, detected_word in enumerate(detected["words"], 1):
            box = detected_word["box"]
            item = {"id": f"word-{i:04d}", "line": detected_word["line"],
                    "box": box, "predicted": "", "confidence": 0,
                    "text": "", "status": "pending", "candidates": []}
            if recognizer is not None:
                try:
                    candidates = recognizer.predict(
                        imaging.crop_pil(img, tuple(box.values())), store.load_lexicon())
                    item["candidates"] = candidates
                    if candidates:
                        item["predicted"] = candidates[0]["text"]
                        item["confidence"] = candidates[0]["confidence"]
                except Exception:
                    app.logger.exception("Falha no reconhecimento da palavra")
            words.append(item)
        record = {
            "id": f"draft-{d['image']}|{record_box[0]}|{record_box[1]}|"
                  f"{record_box[2]}|{record_box[3]}",
            "source_image": d["image"], "box": box_dict(record_box),
            "created_at": None, "updated_at": None, "status": "pending",
            "group_id": d.get("group_id", ""), "lines": detected["lines"],
            "words": words,
        }
        return jsonify(record)

    @app.post("/api/detect-layout")
    def detect_layout():
        d = request.get_json(force=True)
        img = get_image(d["image"])
        detected = layout.detect(img, get_box(d, img))
        return jsonify(detected)

    @app.post("/api/records/save")
    def save_record():
        record = request.get_json(force=True)
        if not record.get("source_image") or not record.get("box"):
            raise ValueError("Registro inválido.")
        previous = records.get(record["id"])
        if previous:
            current_by_id = {w["id"]: w for w in record.get("words", [])}
            for old in previous.get("words", []):
                current = current_by_id.get(old["id"])
                if (current is None or current.get("box") != old.get("box")
                        or current.get("text") != old.get("text")) and old.get("text"):
                    store.delete_confirmation(
                        source=previous["source_image"],
                        box=tuple(old["box"].values()))
        image = get_image(record["source_image"])
        for word in record.get("words", []):
            raw_box = word.get("box")
            if not raw_box:
                if word.get("status") == "reviewed" and word.get("text"):
                    raise ValueError("Palavra revisada sem retângulo.")
                continue
            box = imaging.clamp_box(
                tuple(int(round(float(raw_box[key]))) for key in ("x", "y", "w", "h")),
                image.shape,
            )
            word["box"] = dict(zip(("x", "y", "w", "h"), box))
            if word.get("status") == "reviewed" and word.get("text"):
                store.save_confirmation(
                    source=record["source_image"],
                    box=box,
                    crop=imaging.crop_pil(image, box),
                    text=word["text"], predicted=word.get("predicted", ""),
                    confidence=float(word.get("confidence", 0)))
        record["status"] = "reviewed" if record.get("words") and all(
            w.get("status") == "reviewed" for w in record["words"]) else "pending"
        return jsonify(records.save(record))

    @app.get("/api/records/all")
    def all_records():
        return jsonify(records.all_for(None))

    @app.route("/api/records/<path:record_id>/words/<word_id>",
               methods=["POST", "DELETE"])
    def update_record_word(record_id, word_id):
        record = records.get(record_id)
        if record is None:
            abort(404)
        word = next((w for w in record["words"] if w["id"] == word_id), None)
        if word is None:
            abort(404)
        if request.method == "DELETE":
            record["words"].remove(word)
            store.delete_confirmation(
                source=record["source_image"],
                box=tuple(word["box"].values()))
            record["status"] = "pending"
            return jsonify(records.update(record_id, record))
        d = request.get_json(force=True)
        text = charset.normalize(d.get("text", ""))
        if (err := charset.validate(text)):
            raise ValueError(err)
        word["text"] = text
        word["status"] = "reviewed"
        image = get_image(record["source_image"])
        box = tuple(word["box"].values())
        store.save_confirmation(source=record["source_image"], box=box,
                                crop=imaging.crop_pil(image, box), text=text,
                                predicted=word["predicted"],
                                confidence=float(word["confidence"]))
        if all(w["status"] == "reviewed" for w in record["words"]):
            record["status"] = "reviewed"
        updated = records.update(record_id, record)
        return jsonify(record=updated, word=word)

    @app.post("/api/records/<path:record_id>/layout")
    def update_record_layout(record_id):
        record = records.get(record_id)
        if record is None:
            abort(404)
        payload = request.get_json(force=True)
        words = payload.get("words")
        lines = payload.get("lines")
        if not isinstance(words, list):
            raise ValueError("Lista de palavras inválida.")
        if lines is not None and not isinstance(lines, list):
            raise ValueError("Lista de linhas inválida.")
        old_by_id = {w["id"]: w for w in record["words"]}
        image = get_image(record["source_image"])
        for word in words:
            old = old_by_id.get(word["id"])
            if old and old["box"] != word["box"] and old.get("text"):
                store.delete_confirmation(
                    source=record["source_image"],
                    box=tuple(old["box"].values()))
                store.save_confirmation(
                    source=record["source_image"],
                    box=tuple(word["box"].values()),
                    crop=imaging.crop_pil(image, tuple(word["box"].values())),
                    text=word["text"], predicted=word.get("predicted", ""),
                    confidence=float(word.get("confidence", 0)))
        record["words"] = words
        if lines is not None:
            record["lines"] = lines
        return jsonify(records.update(record_id, record))

    @app.post("/api/records/<path:record_id>/resegment")
    def resegment_record(record_id):
        record = records.get(record_id)
        draft = record is None
        if draft:
            record = request.get_json(force=True)
            if not record.get("source_image"):
                abort(404)
        image = get_image(record["source_image"])
        detected_words = layout.words_for_lines(image, record.get("lines", []))
        words = []
        for i, detected_word in enumerate(detected_words, 1):
            item = {"id": f"word-{i:04d}", "line": detected_word["line"],
                    "box": detected_word["box"], "predicted": "",
                    "confidence": 0, "text": "", "status": "pending",
                    "candidates": []}
            if recognizer is not None:
                try:
                    candidates = recognizer.predict(
                        imaging.crop_pil(image, tuple(item["box"].values())),
                        store.load_lexicon())
                    item["candidates"] = candidates
                    if candidates:
                        item["predicted"] = candidates[0]["text"]
                        item["confidence"] = candidates[0]["confidence"]
                except Exception:
                    app.logger.exception("Falha ao resegmentar palavra")
            words.append(item)
        record["words"] = words
        record["status"] = "pending"
        return jsonify(record if draft else records.update(record_id, record))

    @app.post("/api/recognize")
    def recognize():
        d = request.get_json(force=True)
        img = get_image(d["image"])
        crop = imaging.crop_pil(img, get_box(d, img))
        if recognizer is None:
            return jsonify(candidates=[], warning="Modo sem modelo: digite a transcrição.")
        try:
            return jsonify(candidates=recognizer.predict(crop, store.load_lexicon()))
        except Exception as e:  # modelo ausente, sem torch, sem internet no 1o download...
            app.logger.exception("Falha no reconhecimento")
            return jsonify(candidates=[], warning=f"Modelo indisponível ({type(e).__name__}). Digite a transcrição.")

    @app.post("/api/confirm")
    def confirm():
        d = request.get_json(force=True)
        img = get_image(d["image"])
        box = get_box(d, img)
        text = charset.normalize(d["text"])
        if (err := charset.validate(text)):
            raise ValueError(err)
        row = store.save_confirmation(source=d["image"], box=box, crop=imaging.crop_pil(img, box),
                                      text=text, predicted=d.get("predicted", ""),
                                      confidence=float(d.get("confidence", 0)))
        return jsonify(row=row)

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--no-model", action="store_true", help="so rotulagem manual, sem carregar o modelo")
    a = ap.parse_args()
    print(f"Abra http://127.0.0.1:{a.port}  (imagens em {config.RAW_DIR})")
    create_app(use_model=not a.no_model).run(host="127.0.0.1", port=a.port, threaded=True)


if __name__ == "__main__":
    main()
