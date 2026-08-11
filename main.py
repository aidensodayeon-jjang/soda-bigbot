import os
import sys
import threading
import time

if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2

import audio
import config
import face_db
import proclock
import wake_word
from face_display import SodabotFace
from vision import FaceDetector, SFaceEmbedder

DB_RELOAD_SEC = 30  # register_face.py로 새로 등록된 얼굴을 주기적으로 반영


def vision_loop(app, stop_event):
    detector = FaceDetector()
    embedder = SFaceEmbedder()

    names, matrix = face_db.load_all()
    print("등록된 얼굴:", len(names), "명")

    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("카메라 열기 실패")
        embedder.close()
        return

    last_greeted = {}
    last_reload = time.time()

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                continue

            boxes = detector.detect(frame)

            if not boxes or (boxes[0][3] - boxes[0][1]) < config.MIN_FACE_SIZE:
                app.push_event(("idle",))
                continue

            x1, y1, x2, y2, score = boxes[0]
            face = frame[y1:y2, x1:x2]
            embedding = embedder.embed(face)
            name, similarity = face_db.match_best(embedding, names, matrix)

            now = time.time()

            if name is not None and similarity >= config.MATCH_THRESHOLD:
                if now - last_greeted.get(name, 0) >= config.GREET_COOLDOWN_SEC:
                    last_greeted[name] = now
                    app.push_event(("greet", name))
                    audio.play(audio.pick_random(config.GREETING_SOUNDS_DIR))
                    print("인사:", name, round(similarity, 3))
            else:
                app.push_event(("curious",))

            if now - last_reload > DB_RELOAD_SEC:
                names, matrix = face_db.load_all()
                last_reload = now

    finally:
        cap.release()
        embedder.close()


def main():
    proclock.stop_other(config.REGISTER_PID_FILE, "register_face.py")
    proclock.write_pid(config.MAIN_PID_FILE)

    app = SodabotFace()

    stop_event = threading.Event()
    worker = threading.Thread(target=vision_loop, args=(app, stop_event), daemon=True)
    worker.start()

    # daemon 스레드라 앱 종료 시 arecord가 즉시 안 죽을 수 있음.
    # ponytail: 마이크가 이후 "장치 사용 중"으로 걸리면 stop_event로 정리하는 방식 추가.
    wake_thread = threading.Thread(
        target=wake_word.listen_for_wake_word,
        args=(lambda: app.push_event(("wake",)),),
        daemon=True,
    )
    wake_thread.start()

    try:
        app.run()
    finally:
        stop_event.set()
        proclock.remove_pid(config.MAIN_PID_FILE)


if __name__ == "__main__":
    main()
