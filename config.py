import os

HOME = os.path.expanduser("~")
BASE_DIR = os.path.join(HOME, "sodabot")

# .env (API 키 등 비밀값)를 환경변수로 로드. 자동 시작 등 로그인 셸을 거치지 않는
# 실행 경로에서도 os.environ.get()이 동작하도록 여기서 직접 채워 넣는다.
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _value = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _value.strip())

FACES_DIR = os.path.join(BASE_DIR, "faces")
MODELS_DIR = os.path.join(BASE_DIR, "models")
GREETING_SOUNDS_DIR = os.path.join(BASE_DIR, "sounds", "greeting")

# 얼굴 검출 (OpenCV DNN, Res10 SSD)
DETECTOR_PROTOTXT = os.path.join(MODELS_DIR, "deploy.prototxt")
DETECTOR_MODEL = os.path.join(MODELS_DIR, "res10_300x300_ssd_iter_140000.caffemodel")
DETECT_CONFIDENCE = 0.6
MIN_FACE_SIZE = 70  # px, 이보다 작은(먼) 얼굴은 무시

# 얼굴 인식 (SFace, be-more-agent에서 만든 TensorRT 엔진 재사용)
SFACE_ENGINE = os.path.join(MODELS_DIR, "sface_fp16.engine")
PYCUDA_PATH = os.path.join(
    HOME, "be-more-agent", "pycuda-2021.1", "build", "lib.linux-aarch64-3.6"
)
MATCH_THRESHOLD = 0.45  # 코사인 유사도

# 카메라 (0=CSI imx219, 1=Logitech StreamCam)
CAMERA_INDEX = 1
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

REGISTER_CAMERA_WIDTH = 1280
REGISTER_CAMERA_HEIGHT = 720
REGISTER_SAMPLES = 15
REGISTER_CAPTURE_INTERVAL = 0.6

# 인사
GREET_COOLDOWN_SEC = 120
GREETING_DURATION_MS = 4000

# main.py / register_face.py 동시 실행 방지용 PID 파일
MAIN_PID_FILE = os.path.join(BASE_DIR, ".main.pid")
REGISTER_PID_FILE = os.path.join(BASE_DIR, ".register.pid")

# 스피커 (JieLi BR21 블루투스 스피커, USB 유선 연결)
SPEAKER_DEVICE = "plughw:CARD=BR21,DEV=0"

# GPT 실시간 음성 대화 (OpenAI Realtime API)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
REALTIME_MODEL = "gpt-4o-realtime-preview"
REALTIME_VOICE = "alloy"
CONVERSATION_IDLE_TIMEOUT_SEC = 30  # 응답 없이 이 시간 지나면 세션 종료 (요금 방지)

# 웨이크워드 (PocketSphinx 키워드 스팟팅으로 "hi soda" 감지)
MIC_DEVICE = "plughw:2,0"  # Logitech StreamCam 내장 마이크 (arecord -l 기준)
WAKE_KEYPHRASE = "hi soda"
WAKE_KWS_THRESHOLD = "1e-20"  # 낮을수록(0에 가까울수록) 잘 반응하지만 오탐도 늘어남
