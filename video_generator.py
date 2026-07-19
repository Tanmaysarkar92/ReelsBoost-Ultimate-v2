import os
import logging
from moviepy import ImageClip

logger = logging.getLogger("ReelsBoost")


def generate_video(image_path):
    try:
        os.makedirs("outputs", exist_ok=True)

        output_path = os.path.join("outputs", "reel_video.mp4")

        clip = (
            ImageClip(image_path)
            .with_duration(8)
            .resized(width=1080)
        )

        clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio=False,
            logger="bar"
        )

        return output_path

    except Exception as e:
        logger.exception(e)
        return None