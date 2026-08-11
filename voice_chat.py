import asyncio
import base64
import json
import subprocess

import websockets

import config

REALTIME_URL = "wss://api.openai.com/v1/realtime?model={}".format(config.REALTIME_MODEL)
SAMPLE_RATE = 24000  # Realtime API의 pcm16 기본 샘플레이트


async def _mic_sender(ws, rec_proc):
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, rec_proc.stdout.read, 4800)
        if not chunk:
            break
        await ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(chunk).decode("ascii"),
        }))


async def _receiver(ws, player, on_state):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=config.CONVERSATION_IDLE_TIMEOUT_SEC)
        event = json.loads(raw)
        kind = event.get("type")

        if kind == "response.output_audio.delta":
            player.stdin.write(base64.b64decode(event["delta"]))
            player.stdin.flush()
            on_state("speaking")
        elif kind == "input_audio_buffer.speech_started":
            on_state("thinking")
        elif kind == "response.done":
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
                            "turn_detection": {"type": "server_vad"},
                        },
                        "output": {
                            "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                            "voice": config.REALTIME_VOICE,
                        },
                    },
                },
            }))

            sender_task = asyncio.ensure_future(_mic_sender(ws, rec_proc))
            try:
                await _receiver(ws, player, on_state)
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
