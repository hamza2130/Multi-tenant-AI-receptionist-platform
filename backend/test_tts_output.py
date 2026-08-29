"""
test_tts_output.py

Standalone test: text in, audio file out. No phone call, no browser,
no Twilio involved at all — just confirms ElevenLabs is correctly
configured for this project before touching the full live pipeline.

Same idea as test_tts.py from the voice receptionist project, just
adapted for this project's config.py.

Run with:
    python test_tts_output.py
"""

from elevenlabs.client import ElevenLabs
from config import settings


def main():
    print("=== TTS Output Test ===\n")

    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    sample_text = "Hello! This is Sunrise Clinic's AI receptionist. How can I help you today?"

    print(f"Converting to speech: \"{sample_text}\"")

    audio_stream = client.text_to_speech.convert(
        text=sample_text,
        voice_id=settings.ELEVENLABS_VOICE_ID,
        model_id="eleven_turbo_v2_5",
    )

    output_path = "test_tts_output.mp3"
    with open(output_path, "wb") as f:
        for chunk in audio_stream:
            if chunk:
                f.write(chunk)

    print(f"\n✅ Saved audio to {output_path}")
    print("Play the file to confirm it sounds right.")


if __name__ == "__main__":
    main()
