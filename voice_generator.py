import os
import logging
from elevenlabs.client import ElevenLabs

logger = logging.getLogger("ReelsBoost")

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

# Rachel Voice (Professional English)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def generate_voice(text):

    try:

        os.makedirs("outputs", exist_ok=True)

        output_path = os.path.join("outputs", "voice.mp3")

        audio = client.text_to_speech.convert(
            voice_id=VOICE_ID,
            text=text,
            model_id="eleven_multilingual_v2"
        )

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        logger.info("✅ Voice Generated Successfully")

        return output_path

    except Exception as e:

        logger.exception(e)
        return None