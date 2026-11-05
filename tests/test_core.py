import cv2
import numpy as np
import pytest
from PIL import Image

from recognition.htr import charset, config, imaging, store


def synthetic_page():
    img = np.full((200, 500, 3), 225, np.uint8)  # papel claro
    cv2.putText(img, "Joze", (150, 120), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 2, (30, 30, 30), 3)
    return img


def test_snap_touches_ink_edges():
    img = synthetic_page()
    x, y, w, h = imaging.snap_to_ink(img, (50, 20, 400, 160))
    assert (w, h) != (400, 160) and x >= 50 and y >= 20
    gray = cv2.cvtColor(img[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
    dark = gray < 215  # papel = 225; bordas suavizadas do traço
    assert dark[0].any() and dark[-1].any() and dark[:, 0].any() and dark[:, -1].any()


def test_snap_without_ink_keeps_box():
    blank = np.full((100, 100, 3), 220, np.uint8)
    assert imaging.snap_to_ink(blank, (10, 10, 50, 50)) == (10, 10, 50, 50)


def test_charset():
    assert charset.validate("José") is None
    assert charset.validate("Maria Ferreira")
    assert charset.validate("Jo$e")
    assert charset.validate("")
    assert charset.normalize("Jose\u0301") == "José"


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    for name, rel in (("CONFIRMED_DIR", "c"), ("CROPS_DIR", "c/crops"),
                      ("LABELS_CSV", "c/labels.csv"), ("LEXICON_JSON", "c/lexicon.json"),
                      ("RAW_DIR", "raw")):
        monkeypatch.setattr(config, name, tmp_path / rel)
    (tmp_path / "raw").mkdir()
    return tmp_path


def test_store_roundtrip_and_correction(tmp_data):
    crop = Image.new("RGB", (40, 20), "white")
    store.save_confirmation(source="p1.png", box=(1, 2, 3, 4), crop=crop, text="Joze", predicted="Jose", confidence=0.5)
    store.save_confirmation(source="p1.png", box=(9, 9, 3, 4), crop=crop, text="Joze", predicted="Joze", confidence=0.9)
    assert store.load_lexicon() == {"Joze": 2}
    assert store.load_lexicon() == {"Joze": 2}
    # corrigir o mesmo retangulo substitui, nao duplica
    store.save_confirmation(source="p1.png", box=(1, 2, 3, 4), crop=crop, text="Josepha", predicted="Jose", confidence=0.5)
    assert len(store.boxes_for("p1.png")) == 2
    assert store.load_lexicon() == {"Joze": 1, "Josepha": 1}
    assert len(store.boxes_for("p1.png")) == 2


def test_server_flow(tmp_data):
    from recognition.htr.server import create_app
    cv2.imwrite(str(tmp_data / "raw" / "p1.png"), synthetic_page())
    c = create_app(use_model=False).test_client()
    assert c.get("/api/images").json == ["p1.png"]
    assert c.get("/api/image/p1.png").status_code == 200
    assert c.get("/api/image/../x").status_code == 404
    box = {"x": 50, "y": 20, "w": 400, "h": 160}
    snapped = c.post("/api/snap", json={"image": "p1.png", "box": box}).json
    assert snapped["w"] < 400
    r = c.post("/api/recognize", json={"image": "p1.png", "box": snapped}).json
    assert r["candidates"] == [] and r["warning"]
    assert c.post("/api/confirm", json={"image": "p1.png", "box": snapped, "text": "Jo$e"}).status_code == 400
    ok = c.post("/api/confirm", json={"image": "p1.png", "box": snapped, "text": "Joze"})
    assert ok.status_code == 200
    assert len(c.get("/api/confirmed?image=p1.png").json) == 1


def test_record_flow(tmp_data):
    from recognition.htr.server import create_app
    cv2.imwrite(str(tmp_data / "raw" / "p1.png"), synthetic_page())
    c = create_app(use_model=False).test_client()
    box = {"x": 40, "y": 20, "w": 420, "h": 160}
    r = c.post("/api/records/analyze", json={"image": "p1.png", "box": box})
    assert r.status_code == 200
    record = r.json
    assert record["status"] == "pending"
    assert record["words"]
    word = record["words"][0]
    word["text"] = "Joze"
    word["status"] = "reviewed"
    word["box"] = {key: value + 0.4 for key, value in word["box"].items()}
    saved = c.post("/api/records/save", json=record)
    assert saved.status_code == 200
    assert saved.json["words"][0]["status"] == "reviewed"
    assert all(isinstance(value, int) for value in saved.json["words"][0]["box"].values())
    assert c.get("/api/records?image=p1.png").json[0]["id"] == record["id"]
    moved = dict(word["box"])
    moved["x"] += 2
    word["box"] = moved
    changed = c.post("/api/records/save", json=record)
    assert changed.status_code == 200
    record["words"] = [w for w in record["words"] if w["id"] != word["id"]]
    deleted = c.post("/api/records/save", json=record)
    assert deleted.status_code == 200
    assert all(w["id"] != word["id"] for w in deleted.json["words"])


def test_record_explicit_save(tmp_data):
    from recognition.htr.server import create_app
    cv2.imwrite(str(tmp_data / "raw" / "p1.png"), synthetic_page())
    c = create_app(use_model=False).test_client()
    analyzed = c.post("/api/records/analyze", json={
        "image": "p1.png", "box": {"x": 40, "y": 20, "w": 420, "h": 160}})
    record = analyzed.json
    record["group_id"] = "batismo-1"
    saved = c.post("/api/records/save", json=record)
    assert saved.status_code == 200
    assert c.get("/api/records?image=p1.png").json[0]["group_id"] == "batismo-1"
    assert c.get("/api/records/all").status_code == 200
