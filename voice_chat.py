import asyncio
import base64
import json
import subprocess

import websockets

import config

REALTIME_URL = "wss://api.openai.com/v1/realtime?model={}".format(config.REALTIME_MODEL)
SAMPLE_RATE = 24000  # Realtime API의 pcm16 기본 샘플레이트


async def _mic_sender(ws, rec_proc, speaking):
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, rec_proc.stdout.read, 4800)
        if not chunk:
            break
        if speaking.is_set():
            # 에코 캔슬링이 없는 하드웨어라, 스피커가 말하는 동안은 마이크 입력을
            # 보내지 않는다(안 그러면 마이크가 스피커 소리를 주워서 자기 말에 자기가 반응함).
            continue
        await ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(chunk).decode("ascii"),
        }))


async def _receiver(ws, player, on_state, speaking):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=config.CONVERSATION_IDLE_TIMEOUT_SEC)
        event = json.loads(raw)
        kind = event.get("type")

        if kind == "response.output_audio.delta":
            speaking.set()
            player.stdin.write(base64.b64decode(event["delta"]))
            player.stdin.flush()
            on_state("speaking")
        elif kind == "input_audio_buffer.speech_started":
            on_state("thinking")
        elif kind == "response.done":
            await asyncio.sleep(0.4)  # 스피커에 남은 소리가 다 빠져나갈 시간을 준 뒤 마이크 재개
            speaking.clear()
            on_state("idle")
        elif kind == "error":
            print("Realtime API 오류:", event)


async def _run_session(on_state):
    headers = {"Authorization": "Bearer " + config.OPENAI_API_KEY}

    rec_proc = subprocess.Popen(
        [
            "arecord", "-D", config.MIC_DEVICE,
            "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1",
            "-t", "raw", "-q", "--buffer-time=1000000", "-",
        ],
        stdout=subprocess.PIPE,
    )
    player = subprocess.Popen(
        [
            "aplay", "-q", "-D", config.SPEAKER_DEVICE,
            "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw",
        ],
        stdin=subprocess.PIPE,
    )

    try:
        async with websockets.connect(REALTIME_URL, extra_headers=headers) as ws:
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "model": config.REALTIME_MODEL,
                    "output_modalities": ["audio"],
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                            "turn_detection": {
                                "type": "server_vad",
                                "threshold": 0.6,  # 기본 0.5보다 높여 배경 소음에 덜 반응
                                "silence_duration_ms": 700,  # 말 끊김으로 오판하기 전 대기 시간(기본 500ms)
                            },
                        },
                        "output": {
                            "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                            "voice": config.REALTIME_VOICE,
                        },
                    },
                },
            }))

            speaking = asyncio.Event()
            sender_task = asyncio.ensure_future(_mic_sender(ws, rec_proc, speaking))
            try:
                await _receiver(ws, player, on_state, speaking)
            except asyncio.TimeoutError:
                pass
            finally:
                sender_task.cancel()
    finally:
        rec_proc.terminate()
        player.stdin.close()
        player.terminate()
        on_state("idle")


def start_conversation(on_state=lambda state: None):
    """웨이크워드 감지 콜백에서 호출. 대화가 끝나거나 idle 타임아웃까지 블로킹된다."""
    if not config.OPENAI_API_KEY:
        print("OPENAI_API_KEY가 설정되지 않았습니다.")
        return

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_session(on_state))
    finally:
        loop.close()


def _self_check():
    assert REALTIME_URL.startswith("wss://api.openai.com/v1/realtime")


if __name__ == "__main__":
    _self_check()
    print("자가 점검 통과. 대화를 시작합니다 (Ctrl+C로 종료)...")
    start_conversation(on_state=print)
