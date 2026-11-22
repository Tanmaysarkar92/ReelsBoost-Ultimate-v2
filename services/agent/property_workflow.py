"""Safe bridge between the existing ReelsBoost property pipeline and its Agent.

This module does not change app.py, WhatsApp handling, existing generators,
or publishing modules. The Flask route should call this function after the
customer uploads a property image and submits property details.
"""
from __future__ import annotations

import os
from typing import Any, Callable


def run_property_video_workflow(
    *,
    image_path: str,
    property_details: dict[str, Any],
    caption_generator: Callable[[str], str],
    metadata_generator: Callable[[str, dict[str, Any]], Any] | None = None,
    publish_facebook: bool = False,
    publish_youtube: bool = False,
    publish_confirmed: bool = False,
    voice_generator: Callable[[str], str | None] | None = None,
    video_generator: Callable[[str, str | None], str | None] | None = None,
    facebook_publisher: Callable[..., bool] | None = None,
    youtube_publisher: Callable[..., bool] | None = None,
) -> dict[str, Any]:
    """Create an existing-style property reel and optionally publish it.

    AI caption/metadata functions are injected from app.py so this bridge does
    not guess their implementation or create duplicate AI generation logic.
    Publishing is blocked unless publish_confirmed=True.
    """
    if not image_path or not os.path.isfile(image_path):
        return {"ok": False, "stage": "validate", "error": "image_not_found"}
    if not isinstance(property_details, dict) or not property_details:
        return {"ok": False, "stage": "validate", "error": "property_details_required"}
    if not callable(caption_generator):
        return {"ok": False, "stage": "validate", "error": "caption_generator_required"}

    wants_publish = bool(publish_facebook or publish_youtube)
    if wants_publish and not publish_confirmed:
        # Generate a preview first, but never publish without explicit approval.
        publish_blocked = True
    else:
        publish_blocked = False

    try:
        caption = caption_generator(image_path)
        if not isinstance(caption, str) or not caption.strip():
            return {"ok": False, "stage": "caption", "error": "caption_generation_failed"}

        title = None
        description = None
        if metadata_generator is not None:
            metadata = metadata_generator(image_path, property_details)
            if isinstance(metadata, (tuple, list)) and len(metadata) >= 2:
                title, description = metadata[0], metadata[1]

        if voice_generator is None:
            from voice_generator import generate_voice as voice_generator
        voice_path = voice_generator(caption)
        if not voice_path or not os.path.isfile(voice_path):
            return {"ok": False, "stage": "voice", "error": "voice_generation_failed"}

        if video_generator is None:
            from video_generator import generate_video as video_generator
        video_path = video_generator(image_path, voice_path)
        if not video_path or not os.path.isfile(video_path):
            return {"ok": False, "stage": "video", "error": "video_generation_failed"}

        result: dict[str, Any] = {
            "ok": True,
            "status": "awaiting_publish_confirmation" if publish_blocked else "created",
            "caption": caption,
            "title": title,
            "description": description,
            "voice_path": voice_path,
            "video_path": video_path,
            "published": {"facebook": False, "youtube": False},
        }

        if publish_blocked:
            result["message"] = "Preview created. Explicit customer approval is required before publishing."
            result["requested_publish"] = {
                "facebook": bool(publish_facebook),
                "youtube": bool(publish_youtube),
            }
            return result

        if publish_facebook:
            if facebook_publisher is None:
                from facebook import upload_to_facebook as facebook_publisher
            result["published"]["facebook"] = bool(
                facebook_publisher(video_path, caption)
            )

        if publish_youtube:
            if youtube_publisher is None:
                from youtube import upload_to_youtube as youtube_publisher
            result["published"]["youtube"] = bool(
                youtube_publisher(video_path, title, description)
            )

        if wants_publish and not all(result["published"][p] for p, requested in (
            ("facebook", publish_facebook), ("youtube", publish_youtube)
        ) if requested):
            result["status"] = "publish_failed"
            result["ok"] = False
        elif wants_publish:
            result["status"] = "published"

        return result

    except Exception as exc:
        # Do not leak credentials or environment values in API responses.
        return {
            "ok": False,
            "stage": "workflow",
            "error": "workflow_execution_failed",
            "detail": str(exc)[:240],
        }
