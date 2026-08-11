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
SLEEPY_AFTER_SEC = 120  # 이만큼 아무도 안 보이면 졸린 표정으로 전환

# main.py / register_face.py 동시 실행 방지용 PID 파일
MAIN_PID_FILE = os.path.join(BASE_DIR, ".main.pid")
REGISTER_PID_FILE = os.path.join(BASE_DIR, ".register.pid")

# 스피커 (JieLi BR21 블루투스 스피커, USB 유선 연결)
SPEAKER_DEVICE = "plughw:CARD=BR21,DEV=0"

# 모바일 웹 리모컨
WEB_PORT = 8080

# GPT 음성 대화: "hi soda" 또는 스페이스바로 한 번 녹음 → Whisper 전사 → GPT 응답 → TTS 재생
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CHAT_MODEL = "gpt-4o-mini"
TTS_VOICE = "alloy"
MIC_DEVICE = "plughw:CARD=StreamCam,DEV=0"  # 카드 번호는 재부팅마다 바뀔 수 있어서 이름으로 고정

# 웨이크워드 (PocketSphinx 키워드 스팟팅)
WAKE_KEYPHRASE = "hi soda"
WAKE_KWS_THRESHOLD = "1e-28"  # 작을수록(지수가 더 음수일수록) 더 잘 반응하지만 오탐도 늘어남
