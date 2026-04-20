# ARIA Gateway — Multimodal Handlers (OCR + STT)
#
# Image OCR and audio STT processing.
# Per blueprint §7.4 and sprint plan W1.2.K.
#
# Features:
#   - OCR via pytesseract (optional, graceful degradation)
#   - STT via faster-whisper (optional, lazy load)
#   - Graceful degradation if packages not installed

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from aria.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency availability
# ---------------------------------------------------------------------------

_PYTESSERACT_AVAILABLE: bool = importlib.util.find_spec("pytesseract") is not None
_WHISPER_AVAILABLE: bool = importlib.util.find_spec("faster_whisper") is not None

if _PYTESSERACT_AVAILABLE:
    logger.debug("pytesseract available for OCR")
else:
    logger.warning(
        "pytesseract not installed — OCR will be unavailable. Install with: pip install aria[ml]"
    )

if _WHISPER_AVAILABLE:
    logger.debug("faster-whisper available for STT")
else:
    logger.warning(
        "faster-whisper not installed — STT will be unavailable. Install with: pip install aria[ml]"
    )

# ---------------------------------------------------------------------------
# OCR — pytesseract
# ---------------------------------------------------------------------------


def ocr_image(path: Path) -> str:
    """Run OCR on an image file using pytesseract.

    Args:
        path: Path to the image file (PNG, JPG, TIFF, etc.)

    Returns:
        Extracted text, or empty string if pytesseract is not installed.
    """
    if not _PYTESSERACT_AVAILABLE:
        return ""

    if not path.exists():
        logger.error("OCR image path does not exist: %s", path)
        return ""

    try:
        import pytesseract
        from PIL import Image

        with Image.open(path) as img:
            rgb_img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
            result: str = pytesseract.image_to_string(rgb_img, lang="eng+ita")
            return result.strip()
    except Exception as exc:  # pragma: no cover — degrade gracefully
        logger.error("OCR failed for %s: %s", path, exc)
        return ""


# ---------------------------------------------------------------------------
# STT — faster-whisper
# ---------------------------------------------------------------------------

_whisper_model: object | None = None
_runtime_models_dir: Path | None = None


def _get_runtime_models_dir() -> Path:
    """Return the runtime models directory, creating it if necessary."""
    global _runtime_models_dir  # noqa: PLW0603
    if _runtime_models_dir is None:
        runtime_env = Path(
            __import__("os").environ.get(
                "ARIA_RUNTIME",
                "/home/fulvio/coding/aria/.aria/runtime",
            )
        )
        runtime = runtime_env
        models_dir = runtime / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        _runtime_models_dir = models_dir
    return _runtime_models_dir


@lru_cache(maxsize=1)
def _get_whisper_model() -> object | None:
    """Lazily load the faster-whisper small model and cache it.

    Model files are cached under ``.aria/runtime/models/``.
    Returns None if faster-whisper is not installed.
    """
    if not _WHISPER_AVAILABLE:
        return None

    from faster_whisper import WhisperModel

    models_dir = _get_runtime_models_dir()
    try:
        model = WhisperModel(
            model_size_or_path="small",
            device="auto",
            download_root=str(models_dir),
        )
        logger.info("Whisper model loaded (small) into %s", models_dir)
        return model  # type: ignore[no-any-return]
    except Exception as exc:  # pragma: no cover — degrade gracefully
        logger.error("Failed to load Whisper model: %s", exc)
        return None


def transcribe_audio(path: Path) -> str:
    """Transcribe an audio file using faster-whisper (small model).

    Args:
        path: Path to the audio file (WAV, MP3, OGG, etc.)

    Returns:
        Transcription text, or empty string if faster-whisper is not
        installed or transcription fails.
    """
    model = _get_whisper_model()
    if model is None:
        return ""

    if not path.exists():
        logger.error("Transcribe audio path does not exist: %s", path)
        return ""

    try:
        # Convert ogg/webm to wav if needed (faster-whisper works best with wav)
        ext = path.suffix.lower()
        audio_path = path
        if ext in (".ogg", ".oga", ".webm"):
            wav_path = path.with_suffix(".wav")
            if shutil.which("ffmpeg"):
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(path),
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        str(wav_path),
                    ],
                    capture_output=True,
                    check=False,
                )
                audio_path = wav_path
            else:
                logger.warning("ffmpeg not available for audio conversion, using original file")
        elif ext == ".mp3":
            wav_path = path.with_suffix(".wav")
            if shutil.which("ffmpeg"):
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(path),
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        str(wav_path),
                    ],
                    capture_output=True,
                    check=False,
                )
                audio_path = wav_path

        segments, _info = model.transcribe(  # type: ignore[attr-defined]
            str(audio_path),
            beam_size=5,
            vad_filter=True,
        )
        parts: list[str] = []
        for segment in segments:
            if segment.text:
                parts.append(segment.text.strip())
        transcript = " ".join(parts)
        logger.debug("Transcription for %s: %s", path, transcript[:100])
        return transcript
    except Exception as exc:  # pragma: no cover — degrade gracefully
        logger.error("Transcription failed for %s: %s", path, exc)
        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_ocr_available() -> bool:
    """Return True if OCR (pytesseract) is available."""
    return _PYTESSERACT_AVAILABLE


def is_whisper_available() -> bool:
    """Return True if faster-whisper is available."""
    return _WHISPER_AVAILABLE


def flush_model_cache() -> None:
    """Clear the cached Whisper model (useful for testing or reload)."""
    global _whisper_model  # noqa: PLW0603
    _get_whisper_model.cache_clear()
    _whisper_model = None
