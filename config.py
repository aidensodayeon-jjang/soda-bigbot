import os

HOME = os.path.expanduser("~")
BASE_DIR = os.path.join(HOME, "sodabot")

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

# 웨이크워드 (Vosk 오프라인 음성인식으로 "소다야"/"하이 소다" 감지)
MIC_DEVICE = "plughw:2,0"  # Logitech StreamCam 내장 마이크 (arecord -l 기준)
VOSK_MODEL_DIR = os.path.join(MODELS_DIR, "vosk-model-ko")
