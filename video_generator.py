import os
import logging
import uuid

from moviepy import ImageClip, AudioFileClip

logger = logging.getLogger("ReelsBoost")


def generate_video(image_path, voice_path=None):

    try:

        # ==================================================
        # VALIDATE IMAGE
        # ==================================================

        if not image_path:

            logger.error(
                "❌ Image path is missing"
            )

            return None

        if not os.path.exists(image_path):

            logger.error(
                f"❌ Image not found: {image_path}"
            )

            return None

        # ==================================================
        # VALIDATE VOICE
        # ==================================================

        if voice_path:

            if not os.path.exists(voice_path):

                logger.warning(
                    f"⚠️ Voice file not found: {voice_path}"
                )

                voice_path = None

        # ==================================================
        # OUTPUT FOLDER
        # ==================================================

        os.makedirs(
            "outputs",
            exist_ok=True
        )

        # ==================================================
        # UNIQUE OUTPUT FILE
        # ==================================================

        unique_id = uuid.uuid4().hex[:8]

        output_path = os.path.join(
            "outputs",
            f"reel_{unique_id}.mp4"
        )

        logger.info(
            f"🎬 Video output: {output_path}"
        )

        # ==================================================
        # CREATE IMAGE CLIP
        # ==================================================

        logger.info(
            "🖼️ Creating image clip..."
        )

        clip = (
            ImageClip(image_path)
            .with_duration(8)
            .resized(width=1080)
        )

        # ==================================================
        # ADD VOICE
        # ==================================================

        if voice_path:

            logger.info(
                f"🎤 Adding voice: {voice_path}"
            )

            audio = AudioFileClip(
                voice_path
            )

            # Make video duration match audio
            duration = min(
                8,
                audio.duration
            )

            clip = clip.with_duration(
                duration
            )

            clip = clip.with_audio(
                audio
            )

        # ==================================================
        # WRITE VIDEO
        # ==================================================

        logger.info(
            "🎥 Rendering MP4..."
        )

        clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger="bar"
        )

        # ==================================================
        # CLOSE RESOURCES
        # ==================================================

        try:
            clip.close()
        except Exception:
            pass

        logger.info(
            f"✅ Video generated successfully: {output_path}"
        )

        return output_path

    except Exception as e:

        logger.exception(
            f"❌ Video generation failed: {e}"
        )

        return None