import os
import logging
import uuid
import subprocess
import imageio_ffmpeg

logger = logging.getLogger("ReelsBoost")


def generate_video(image_path, voice_path=None):

    try:

        if not image_path or not os.path.exists(image_path):
            logger.error(f"❌ Image not found: {image_path}")
            return None

        if voice_path and not os.path.exists(voice_path):
            logger.warning(f"⚠️ Voice not found: {voice_path}")
            voice_path = None

        os.makedirs("outputs", exist_ok=True)

        output_path = os.path.join(
            "outputs",
            f"reel_{uuid.uuid4().hex[:8]}.mp4"
        )

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        logger.info(f"🎬 FFmpeg: {ffmpeg}")
        logger.info(f"🎬 Video output: {output_path}")

        if voice_path:

            command = [
                ffmpeg,
                "-y",
                "-loop", "1",
                "-i", image_path,
                "-i", voice_path,
                "-t", "8",
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-shortest",
                output_path
            ]

        else:

            command = [
                ffmpeg,
                "-y",
                "-loop", "1",
                "-i", image_path,
                "-t", "8",
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                output_path
            ]

        logger.info("🎥 Starting FFmpeg rendering...")

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            logger.error("❌ FFmpeg failed")
            logger.error(result.stderr[-3000:])
            return None

        if not os.path.exists(output_path):
            logger.error("❌ MP4 was not created")
            return None

        size = os.path.getsize(output_path)

        logger.info(
            f"✅ Video generated successfully: "
            f"{output_path} ({size} bytes)"
        )

        return output_path

    except Exception as e:

        logger.exception(
            f"❌ Video generation error: {e}"
        )

        return None