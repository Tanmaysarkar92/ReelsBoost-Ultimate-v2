import os
import asyncio
import logging
import edge_tts

logger = logging.getLogger("ReelsBoost")

# Microsoft Edge TTS voice
VOICE = "en-US-AriaNeural"


def generate_voice(text):

    try:

        os.makedirs("outputs", exist_ok=True)

        output_path = os.path.join("outputs", "voice.mp3")

        async def create_voice():

            communicate = edge_tts.Communicate(
                text=text,
                voice=VOICE
            )

            await communicate.save(output_path)

        asyncio.run(create_voice())

        logger.info("✅ Voice Generated Successfully")

        return output_path

    except Exception as e:

        logger.exception("❌ TTS Error")

        return None
