import os
import logging
import uuid
import subprocess
import imageio_ffmpeg

logger = logging.getLogger("ReelsBoost")


def generate_video(image_path, voice_path=None):

    try:

        # ==========================
        # Check image
        # ==========================

        if not image_path or not os.path.exists(image_path):

            logger.error(
                f"❌ Image not found: {image_path}"
            )

            return None

        # ==========================
        # Check voice
        # ==========================

        if voice_path and not os.path.exists(voice_path):

            logger.warning(
                f"⚠️ Voice not found: {voice_path}"
            )

            voice_path = None

        # ==========================
        # Create output folder
        # ==========================

        os.makedirs(
            "outputs",
            exist_ok=True
        )

        output_path = os.path.join(
            "outputs",
            f"reel_{uuid.uuid4().hex[:8]}.mp4"
        )

        # ==========================
        # FFmpeg
        # ==========================

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        logger.info(
            f"🎬 FFmpeg: {ffmpeg}"
        )

        logger.info(
            f"🎬 Video output: {output_path}"
        )

        # ==================================================
        # ANIMATED IMAGE FILTER
        # ==================================================
        #
        # Slow zoom + horizontal movement.
        #
        # The image starts slightly zoomed out
        # and gradually zooms in.
        #
        # This makes the Reel look like a real video
        # instead of a static photograph.
        #
        # ==================================================

        video_filter = (
    "scale=1600:2844:force_original_aspect_ratio=increase,"
    "zoompan="
    "z='1.0+0.18*on/192':"
    "x='(iw-iw/zoom)/2+90*sin(on/45)':"
    "y='(ih-ih/zoom)/2+60*cos(on/50)':"
    "d=1:"
    "s=1080x1920:"
    "fps=24,"
    "setsar=1"
)

        # ==========================
        # Video + Voice
        # ==========================

        if voice_path:

            command = [

                ffmpeg,

                "-y",

                # Image
                "-loop",
                "1",

                "-i",
                image_path,

                # Voice
                "-i",
                voice_path,

                # Duration
                "-t",
                "8",

                # Animation
                "-vf",
                video_filter,

                # Video
                "-r",
                "24",

                "-c:v",
                "libx264",

                "-preset",
                "ultrafast",

                "-threads",
                "1",

                "-pix_fmt",
                "yuv420p",

                # Audio
                "-c:a",
                "aac",

                "-b:a",
                "128k",

                "-shortest",

                "-movflags",
                "+faststart",

                output_path
            ]

        # ==========================
        # Video without Voice
        # ==========================

        else:

            command = [

                ffmpeg,

                "-y",

                "-loop",
                "1",

                "-i",
                image_path,

                "-t",
                "8",

                "-vf",
                video_filter,

                "-r",
                "24",

                "-c:v",
                "libx264",

                "-preset",
                "ultrafast",

                "-threads",
                "1",

                "-pix_fmt",
                "yuv420p",

                "-movflags",
                "+faststart",

                output_path
            ]

        # ==========================
        # Render
        # ==========================

        logger.info(
            "🎥 Starting animated FFmpeg rendering..."
        )

        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True
        )

        # ==========================
        # FFmpeg Error
        # ==========================

        if result.returncode != 0:

            logger.error(
                "❌ FFmpeg failed"
            )

            logger.error(
                result.stderr[-3000:]
            )

            return None

        # ==========================
        # Check output
        # ==========================

        if not os.path.exists(output_path):

            logger.error(
                "❌ MP4 was not created"
            )

            return None

        size = os.path.getsize(
            output_path
        )

        logger.info(
            f"✅ Animated video generated successfully: "
            f"{output_path} ({size} bytes)"
        )

        return output_path

    except Exception as e:

        logger.exception(
            f"❌ Video generation error: {e}"
        )

        return None