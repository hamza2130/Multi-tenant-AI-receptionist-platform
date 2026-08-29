"""
test_stt_input.py

Standalone test: audio file in, text out. Confirms Deepgram is
correctly configured for this project. Run test_tts_output.py first
to generate a sample audio file, then run this to transcribe it back.

Run with:
    python test_tts_output.py
    python test_stt_input.py
"""

import sys
from deepgram import DeepgramClient
from config import settings


def main():
    print("=== STT Input Test ===\n")

    file_path = sys.argv[1] if len(sys.argv) > 1 else "test_tts_output.mp3"

    client = DeepgramClient(api_key=settings.DEEPGRAM_API_KEY)

    print(f"Transcribing: {file_path}")
    try:
        with open(file_path, "rb") as audio_file:
            response = client.listen.v1.media.transcribe_file(
                request=audio_file.read(),
                model="nova-3",
            )
    except FileNotFoundError:
        print(f"\n❌ Couldn't find {file_path}.")
        print("Run 'python test_tts_output.py' first to generate a sample file.")
        return

    transcript = response.results.channels[0].alternatives[0].transcript
    print(f"\n✅ Transcript: \"{transcript}\"")


if __name__ == "__main__":
    main()
