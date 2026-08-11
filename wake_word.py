import subprocess

from pocketsphinx import Decoder

import config


def _make_decoder():
    ps_config = Decoder.default_config()
    ps_config.set_string("-lm", None)  # 기본 언어모델을 끄고 키워드 스팟팅 모드로 전환
    ps_config.set_string("-keyphrase", config.WAKE_KEYPHRASE)
    ps_config.set_float("-kws_threshold", float(config.WAKE_KWS_THRESHOLD))
    ps_config.set_string("-logfn", "/dev/null")
    return Decoder(ps_config)


def listen_for_wake_word(on_detected):
    """마이크 입력을 스트리밍하며 웨이크워드가 들리면 on_detected()를 호출한다."""
    decoder = _make_decoder()

    rec = subprocess.Popen(
        [
            "arecord", "-D", config.MIC_DEVICE,
            "-f", "S16_LE", "-r", "16000", "-c", "1",
            "-t", "raw", "-q", "-",
        ],
        stdout=subprocess.PIPE,
    )

    decoder.start_utt()
    try:
        while True:
            buf = rec.stdout.read(1024)
            if not buf:
                break

            decoder.process_raw(buf, False, False)

            if decoder.hyp() is not None:
                on_detected()
                decoder.end_utt()
                decoder.start_utt()
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
