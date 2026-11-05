"""Execução do pipeline Kraken sem acoplar a interface web ao CLI."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class KrakenError(RuntimeError):
    """Erro explícito ao executar o Kraken ou validar seus artefatos."""


@dataclass(frozen=True)
class KrakenResult:
    """Resultado persistido de uma execução do pipeline."""

    output: Path
    command: tuple[str, ...]
    stdout: str
    stderr: str


def executable() -> str:
    """Retorna o executável configurado e falha com instrução acionável."""
    command = os.environ.get("KRAKEN_COMMAND", "kraken")
    resolved = shutil.which(command)
    if resolved is None and command == "kraken":
        venv_executable = Path(sys.executable).with_name(
            "kraken.exe" if os.name == "nt" else "kraken")
        if venv_executable.is_file():
            resolved = str(venv_executable)
    if resolved is None:
        raise KrakenError(
            f"Executável Kraken não encontrado: {command!r}. "
            "Instale-o no ambiente ativo com 'pip install kraken'.")
    return resolved


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise KrakenError(f"{label} não encontrado: {path}")


def build_pipeline_command(
    image: Path,
    output: Path,
    segmentation_model: Path,
    recognition_model: Path,
    *,
    device: str | None = None,
) -> list[str]:
    """Monta segmentação neural + reconhecimento com saída PageXML."""
    _require_file(image, "Imagem de entrada")
    _require_file(segmentation_model, "Modelo de segmentação")
    _require_file(recognition_model, "Modelo de reconhecimento")
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        executable(),
        "--pagexml",
        "--raise-on-error",
        "-i", str(image), str(output),
        "segment", "--baseline", "-i", str(segmentation_model),
        "ocr", "-m", str(recognition_model),
    ]
    if device:
        command[1:1] = ["--device", device]
    return command


def run_pipeline(
    image: Path,
    output: Path,
    segmentation_model: Path,
    recognition_model: Path,
    *,
    device: str | None = None,
    timeout: int = 1800,
) -> KrakenResult:
    """Executa o Kraken e retorna o PageXML para revisão/importação."""
    command = build_pipeline_command(
        image, output, segmentation_model, recognition_model, device=device)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise KrakenError(
            f"Kraken excedeu o limite de {timeout} segundos.") from exc
    except OSError as exc:
        raise KrakenError(f"Falha ao iniciar o Kraken: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise KrakenError(
            f"Kraken terminou com código {completed.returncode}: {detail}")
    _require_file(output, "Saída PageXML do Kraken")
    return KrakenResult(
        output=output,
        command=tuple(command),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def command_available() -> bool:
    """Indica somente se o executável está disponível no PATH."""
    try:
        executable()
    except KrakenError:
        return False
    return True
