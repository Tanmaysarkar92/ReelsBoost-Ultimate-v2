import os
import asyncio
import logging
import uuid

import edge_tts

logger = logging.getLogger("ReelsBoost")


# ============================================================
# MICROSOFT EDGE TTS VOICE
# ============================================================

VOICE = "en-US-AriaNeural"


# ============================================================
# GENERATE VOICE
# ============================================================

def generate_voice(text):

    try:

        # ====================================================
        # OUTPUT FOLDER
        # ====================================================

        os.makedirs(
            "outputs",
            exist_ok=True
        )

        # ====================================================
        # UNIQUE AUDIO FILE
        # ====================================================

        unique_id = uuid.uuid4().hex[:8]

        output_path = os.path.join(
            "outputs",
            f"voice_{unique_id}.mp3"
        )

        logger.info(
            f"🎤 Generating Edge TTS voice..."
        )

        # ====================================================
        # ASYNC TTS
        # ====================================================

        async def create_voice():

            communicate = edge_tts.Communicate(
                text=text,
                voice=VOICE
            )

            await communicate.save(
                output_path
            )

        asyncio.run(
            create_voice()
        )

        # ====================================================
        # VERIFY FILE
        # ====================================================

        if not os.path.exists(
            output_path
        ):

            logger.error(
                "❌ TTS file was not created"
            )

            return None

        logger.info(
            f"✅ Voice Generated Successfully: {output_path}"
        )

        return output_path

    except Exception as e:

        logger.exception(
            f"❌ TTS Error: {e}"
        )

        return None