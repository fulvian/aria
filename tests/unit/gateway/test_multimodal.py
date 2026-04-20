"""Unit tests for gateway multimodal module (W1.2.K)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest

from aria.gateway.multimodal import (
    ocr_image,
    transcribe_audio,
    is_ocr_available,
    is_whisper_available,
    flush_model_cache,
)


class TestOcrImage:
    """Tests for ocr_image function."""

    def test_returns_empty_string_when_pytesseract_not_available(self) -> None:
        """OCR should return empty string gracefully when pytesseract is not installed."""
        with patch("aria.gateway.multimodal._PYTESSERACT_AVAILABLE", False):
            result = ocr_image(Path("/nonexistent/image.png"))
            assert result == ""

    def test_returns_empty_string_for_nonexistent_path(self) -> None:
        """OCR should return empty string for non-existent files."""
        result = ocr_image(Path("/nonexistent/image.png"))
        assert result == ""


class TestTranscribeAudio:
    """Tests for transcribe_audio function."""

    def test_returns_empty_string_when_whisper_not_available(self) -> None:
        """STT should return empty string gracefully when faster-whisper is not installed."""
        with patch("aria.gateway.multimodal._WHISPER_AVAILABLE", False):
            result = transcribe_audio(Path("/nonexistent/audio.wav"))
            assert result == ""

    def test_returns_empty_string_for_nonexistent_path(self) -> None:
        """STT should return empty string for non-existent files."""
        result = transcribe_audio(Path("/nonexistent/audio.wav"))
        assert result == ""


class TestAvailabilityHelpers:
    """Tests for availability check functions."""

    def test_is_ocr_available_returns_bool(self) -> None:
        """is_ocr_available should return a bool."""
        result = is_ocr_available()
        assert isinstance(result, bool)

    def test_is_whisper_available_returns_bool(self) -> None:
        """is_whisper_available should return a bool."""
        result = is_whisper_available()
        assert isinstance(result, bool)


class TestFlushModelCache:
    """Tests for flush_model_cache function."""

    def test_flush_model_cache_does_not_raise(self) -> None:
        """flush_model_cache should not raise any exception."""
        flush_model_cache()  # should not raise
