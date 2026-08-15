import audioop
import os
import subprocess
import tempfile
import wave

import requests

import config

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1600  # 0.1초 분량
SILENCE_RMS_THRESHOLD = 600  # 배경 소음(TV 등)을 발화로 오인하지 않도록 상향
SILENCE_HANG_SEC = 1.2  # 말이 끝났다고 판단하기까지 기다리는 무음 길이
MAX_RECORD_SEC = 10
_SILENCE_LIMIT = int(SILENCE_HANG_SEC / (CHUNK_SAMPLES / SAMPLE_RATE))
_MAX_CHUNKS = int(MAX_RECORD_SEC / (CHUNK_SAMPLES / SAMPLE_RATE))

SYSTEM_PROMPT = "너는 소다봇이라는 작은 탁상 로봇이야. 짧고 친근하게 한국어로 대답해."


def _collect_frames(chunks):
    """오디오 조각들을 모으다가, 말이 시작된 뒤 무음이 길게 이어지면 멈춘다.
    한 번도 목소리가 감지되지 않았으면 None을 반환한다 (배경 소음뿐이었던 경우)."""
    frames = []
    silence_chunks = 0
    heard_voice = False

    for chunk in chunks:
        frames.append(chunk)

        if audioop.rms(chunk, 2) >= SILENCE_RMS_THRESHOLD:
            heard_voice = True
            silence_chunks = 0
        elif heard_voice:
            silence_chunks += 1
            if silence_chunks >= _SILENCE_LIMIT:
                break

    return frames if heard_voice else None


def _record_utterance():
    rec = subprocess.Popen(
        [
            "arecord", "-D", config.MIC_DEVICE,
            "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1",
            "-t", "raw", "-q", "-",
        ],
        stdout=subprocess.PIPE,
    )

    def _chunks():
        for _ in range(_MAX_CHUNKS):
            chunk = rec.stdout.read(CHUNK_SAMPLES * 2)
            if not chunk:
                return
            yield chunk

    try:
        frames = _collect_frames(_chunks())
    finally:
        rec.terminate()
        rec.wait()

    if not frames:
        return None

    path = tempfile.mktemp(suffix=".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(frames))
    return path


def _transcribe(wav_path):
    with open(wav_path, "rb") as f:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": "Bearer " + config.OPENAI_API_KEY},
            files={"file": ("speech.wav", f, "audio/wav")},
            data={"model": "whisper-1"},
            timeout=20,
        )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


def _chat_reply(user_text):
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": "Bearer " + config.OPENAI_API_KEY},
        json={
            "model": config.CHAT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def speak(text, on_start=lambda: None):
    """on_start는 TTS 요청 시점이 아니라 실제 오디오가 스피커로 나가기 시작할 때 불린다
    (입 모양 애니메이션이 네트워크 지연 동안 미리 시작되는 걸 방지)."""
    resp = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": "Bearer " + config.OPENAI_API_KEY},
        json={
            "model": "tts-1",
            "voice": config.TTS_VOICE,
            "input": text,
            "response_format": "wav",
        },
        timeout=30,
        stream=True,
    )
    resp.raise_for_status()

    # 전체 응답을 다 받고 재생하면 체감 지연이 크므로, 도착하는 대로 바로 흘려보낸다.
    player = subprocess.Popen(
        ["aplay", "-q", "-D", config.SPEAKER_DEVICE, "-"], stdin=subprocess.PIPE,
    )
    started = False
    for chunk in resp.iter_content(chunk_size=4096):
        if chunk:
            if not started:
                on_start()
                started = True
            player.stdin.write(chunk)
    player.stdin.close()
    player.wait()


def start_conversation(on_state=lambda state: None):
    """웨이크워드 감지 콜백에서 호출. "hi soda" 한 번에 딱 한 번만 듣고 답한다
    (계속 듣지 않고, 다음 대화를 하려면 다시 "hi soda"라고 불러야 한다)."""
    if not config.OPENAI_API_KEY:
        print("OPENAI_API_KEY가 설정되지 않았습니다.")
        return

    on_state("thinking")
    wav_path = _record_utterance()
    if not wav_path:
        on_state("idle")
        return

    try:
        user_text = _transcribe(wav_path)
        if not user_text:
            return

        print("사용자:", user_text)
        reply = _chat_reply(user_text)
        print("소다봇:", reply)

        speak(reply, on_start=lambda: on_state("speaking"))
    finally:
        os.remove(wav_path)
        on_state("idle")


def _self_check():
    import struct

    def _tone(level):
        return struct.pack("<{}h".format(CHUNK_SAMPLES), *([level] * CHUNK_SAMPLES))

    loud, silent = _tone(10000), _tone(0)

    frames = _collect_frames([loud, loud] + [silent] * (_SILENCE_LIMIT + 2))
    assert frames is not None
    assert len(frames) == 2 + _SILENCE_LIMIT  # 무음이 길게 이어지면 그 지점에서 멈춰야 함

    assert _collect_frames([silent] * 5) is None  # 목소리 없이 소음만 있었으면 스킵


if __name__ == "__main__":
    _self_check()
    print("자가 점검 통과. 대화를 시작합니다...")
    start_conversation(on_state=print)
