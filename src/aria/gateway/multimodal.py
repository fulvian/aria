# Multimodal — Multimodal processing support
#
# Stub implementation for multimodal processing.
#
# Usage:
#   from aria.gateway.multimodal import process_image, process_voice
#
#   result = await process_image(image_bytes)

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def process_image(image_data: bytes) -> dict:
    """Process an image.

    Args:
        image_data: Raw image bytes

    Returns:
        Dict with processed image info
    """
    logger.debug("Would process image of size %d bytes", len(image_data))
    return {"processed": True, "size": len(image_data)}


async def process_voice(audio_data: bytes) -> dict:
    """Process a voice message.

    Args:
        audio_data: Raw audio bytes

    Returns:
        Dict with transcribed text
    """
    logger.debug("Would process audio of size %d bytes", len(audio_data))
    return {"transcribed": "stub transcription", "language": "it"}
