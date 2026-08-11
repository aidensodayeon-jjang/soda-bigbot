import audioop
import subprocess
from collections import deque

from pocketsphinx import Decoder

import config

# TV/스피커에서 나오는 배경 소음은 대체로 사용자가 직접 부를 때보다 마이크에
# 작게 들어온다. 그래서 KWS 임계값은 느슨하게 열어 실제 "hi soda"를 잘 잡되,
# 감지 순간 음량이 이 값보다 작으면(=먼 곳 소리로 추정) 무시한다.
MIN_DETECT_RMS = 150


def _make_decoder():
    ps_config = Decoder.default_config()
    ps_config.set_string("-lm", None)  # 기본 언어모델을 끄고 키워드 스팟팅 모드로 전환
    ps_config.set_string("-keyphrase", config.WAKE_KEYPHRASE)
    ps_config.set_float("-kws_threshold", float(config.WAKE_KWS_THRESHOLD))
    ps_config.set_string("-logfn", "/dev/null")
    return Decoder(ps_config)


def _open_mic():
    return subprocess.Popen(
        [
            "arecord", "-D", config.MIC_DEVICE,
            "-f", "S16_LE", "-r", "16000", "-c", "1",
            "-t", "raw", "-q",
            "--buffer-time=1000000",  # 카메라 인식과 CPU를 나눠 쓸 때 오버런 방지용 여유 버퍼(1초)
            "-",
        ],
        stdout=subprocess.PIPE,
    )


def listen_for_wake_word(on_detected):
    """마이크 입력을 스트리밍하며 웨이크워드가 들리면 on_detected()를 호출한다.

    on_detected()를 부르는 동안은 마이크를 놓아줘서(arecord 종료), 대화 세션 등
    같은 마이크 장치를 쓰는 다른 코드가 그 사이에 열 수 있게 한다.
    """
    decoder = _make_decoder()
    rec = _open_mic()
    recent_rms = deque(maxlen=30)  # 약 1초 분량, 발화 순간의 음량을 판단하기 위함

    decoder.start_utt()
    try:
        while True:
            buf = rec.stdout.read(1024)
            if not buf:
                break

            recent_rms.append(audioop.rms(buf, 2))
            decoder.process_raw(buf, False, False)

            if decoder.hyp() is not None:
                loud_enough = max(recent_rms) >= MIN_DETECT_RMS
                decoder.end_utt()

                if not loud_enough:
                    # 가까이서 부른 게 아니라 TV 등 먼 배경음일 가능성이 커서 무시
                    decoder.start_utt()
                    continue

                rec.terminate()
                rec.wait()

                on_detected()

                decoder.start_utt()
                rec = _open_mic()
    finally:
        rec.terminate()


def _self_check():
    decoder = _make_decoder()
    decoder.start_utt()
    decoder.end_utt()


if __name__ == "__main__":
    _self_check()
    print("자가 점검 통과. 실시간 감지를 시작합니다 (Ctrl+C로 종료, '{}'라고 말해보세요)...".format(config.WAKE_KEYPHRASE))
    listen_for_wake_word(lambda: print(">>> 웨이크워드 감지!"))
