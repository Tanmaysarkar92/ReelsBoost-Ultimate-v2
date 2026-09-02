import os
import logging
import uuid
import subprocess
import imageio_ffmpeg

logger = logging.getLogger("ReelsBoost")


# ============================================================
# SETTINGS
# ============================================================

VIDEO_DURATION = 10.5
OUTRO_DURATION = 2.5

CONTACT_PHONE = os.getenv(
    "CONTACT_PHONE",
    "+91 XXXXX XXXXX"
)


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
        # MAIN PROPERTY ANIMATION
        # ==================================================

        main_filter = (
            "scale=1600:2844:"
            "force_original_aspect_ratio=increase,"
            "zoompan="
            "z='min(1.0+0.28*on/48,1.28)':"
            "x='(iw-iw/zoom)/2+90*sin(on/45)':"
            "y='(ih-ih/zoom)/2+60*cos(on/50)':"
            "d=1:"
            "s=1080x1920:"
            "fps=24,"
            "setsar=1"
        )

        # ==================================================
        # OUTRO
        # ==================================================

        # Use simple text without special filter expressions.
        # This avoids FFmpeg parsing problems.

        outro_filter = (
    "color=c=black:s=1080x1920:r=24,"
    "trim=duration=2.5,"
    "setpts=PTS-STARTPTS[outro]"
)

        # ==================================================
        # MAIN VIDEO DURATION
        # ==================================================

        main_duration = VIDEO_DURATION - OUTRO_DURATION

        # ==================================================
        # VIDEO + VOICE
        # ==================================================

        if voice_path:

            filter_complex = (
                f"[0:v]{main_filter},"
                f"trim=duration={main_duration},"
                "setpts=PTS-STARTPTS[main];"

                f"{outro_filter};"

                "[main][outro]"
                "concat=n=2:v=1:a=0,"
                "format=yuv420p[v]"
            )

            command = [

                ffmpeg,

                "-y",

                # Property image
                "-loop",
                "1",

                "-i",
                image_path,

                # Voice
                "-i",
                voice_path,

                # Filters
                "-filter_complex",
                filter_complex,

                # Video
                "-map",
                "[v]",

                # Audio
                "-map",
                "1:a",

                # Final duration
                "-t",
                str(VIDEO_DURATION),

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

                # Do NOT use -shortest.
                # Outro must remain visible.

                "-movflags",
                "+faststart",

                output_path
            ]

        # ==================================================
        # VIDEO WITHOUT VOICE
        # ==================================================

        else:

            filter_complex = (
                f"[0:v]{main_filter},"
                f"trim=duration={main_duration},"
                "setpts=PTS-STARTPTS[main];"

                f"{outro_filter};"

                "[main][outro]"
                "concat=n=2:v=1:a=0,"
                "format=yuv420p[v]"
            )

            command = [

                ffmpeg,

                "-y",

                "-loop",
                "1",

                "-i",
                image_path,

                "-filter_complex",
                filter_complex,

                "-map",
                "[v]",

                "-t",
                str(VIDEO_DURATION),

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
            "🎥 Starting 10.5 second video rendering..."
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
                result.stderr[-5000:]
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
            f"✅ 10.5 second video generated successfully: "
            f"{output_path} ({size} bytes)"
        )

        return output_path

    except Exception as e:

        logger.exception(
            f"❌ Video generation error: {e}"
        )

        return None