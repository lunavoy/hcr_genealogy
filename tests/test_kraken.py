from pathlib import Path

import pytest

import segmentation.kraken as kraken
from segmentation.kraken import KrakenError, build_pipeline_command


def test_pipeline_command_requires_existing_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KRAKEN_COMMAND", "kraken-test")
    with pytest.raises(KrakenError, match="Imagem de entrada"):
        build_pipeline_command(
            tmp_path / "page.jpg",
            tmp_path / "result.xml",
            tmp_path / "segment.mlmodel",
            tmp_path / "recognize.mlmodel",
        )


def test_pipeline_command_uses_pagexml_and_baselines(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(kraken, "executable", lambda: "kraken-test")
    image = tmp_path / "page.jpg"
    segmentation = tmp_path / "segment.mlmodel"
    recognition = tmp_path / "recognize.mlmodel"
    for path in (image, segmentation, recognition):
        path.write_bytes(b"fixture")

    command = build_pipeline_command(
        image,
        tmp_path / "result.xml",
        segmentation,
        recognition,
        device="cpu",
    )

    assert command[0] == "kraken-test"
    assert "--pagexml" in command
    assert "--baseline" in command
    assert "ocr" in command
    assert "--device" in command
