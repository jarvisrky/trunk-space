import socket
import wave
import subprocess
import tempfile
import json
import datetime
import os

# ===== CONFIG =====
UDP_PORT = 9123
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit
WHISPER_BIN = "./whisper.cpp/main"
WHISPER_MODEL = "./whisper.cpp/models/ggml-base.en.bin"
LOG_FILE = "radio_transcripts.jsonl"
# ==================

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", UDP_PORT))

print(f"[+] Listening for Trunk Recorder audio on UDP {UDP_PORT}")

def transcribe_pcm(pcm_bytes):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_bytes)

        wav_path = tmp.name

    result = subprocess.run(
        [
            WHISPER_BIN,
            "-m", WHISPER_MODEL,
            "-f", wav_path,
            "--no-timestamps"
        ],
        capture_output=True,
        text=True
    )

    os.unlink(wav_path)
    return result.stdout.strip()

buffer = bytearray()

while True:
    data, addr = sock.recvfrom(4096)

    # Simple heuristic:
    # Trunk Recorder sends JSON control packets too
    if data.startswith(b"{"):
        event = json.loads(data.decode())

        if event.get("type") == "call_end":
            if buffer:
                text = transcribe_pcm(buffer)

                if text:
                    log_entry = {
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "talkgroup": event.get("talkgroup"),
                        "frequency": event.get("frequency"),
                        "system": event.get("system"),
                        "transcript": text
                    }

                    print(log_entry)

                    with open(LOG_FILE, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")

                buffer.clear()
        continue

    # PCM audio
    buffer.extend(data)
