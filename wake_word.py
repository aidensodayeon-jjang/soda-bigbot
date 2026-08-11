import json
import subprocess

import vosk

import config

vosk.SetLogLevel(-1)

SAMPLE_RATE = 16000
WAKE_PHRASES = ["소다야", "하이 소다", "hi soda"]


def _contains_wake_word(text):
    text = text.replace(" ", "")
    return any(phrase.replace(" ", "") in text for phrase in WAKE_PHRASES)


def listen_for_wake_word(on_detected):
    """Vosk로 마이크 입력을 실시간 전사하며 웨이크워드가 들리면 on_detected()를 호출한다."""
    model = vosk.Model(config.VOSK_MODEL_DIR)
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

    rec = subprocess.Popen(
        [
            "arecord", "-D", config.MIC_DEVICE,
            "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1",
            "-t", "raw", "-q", "-",
        ],
        stdout=subprocess.PIPE,
    )

    try:
        while True:
            data = rec.stdout.read(4000)
            if not data:
                break

            if recognizer.AcceptWaveform(data):
                text = json.loads(recognizer.Result()).get("text", "")
            else:
                text = json.loads(recognizer.PartialResult()).get("partial", "")

            if text and _contains_wake_word(text):
                on_detected()
                recognizer.Reset()
    finally:
        rec.terminate()


def _self_check():
    assert _contains_wake_word("소다야 뭐해")
    assert _contains_wake_word("하이 소다 안녕")
    assert _contains_wake_word("hi soda turn on the light")
    assert not _contains_wake_word("안녕하세요")


if __name__ == "__main__":
    _self_check()
    print("자가 점검 통과. 실시간 감지를 시작합니다 (Ctrl+C로 종료)...")
    listen_for_wake_word(lambda: print(">>> 웨이크워드 감지!"))
