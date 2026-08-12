import datetime
import glob
import os
import queue
import sys
import tempfile
import threading
import time

if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np

import config
import drive_upload
import face_db
import proclock
import voice_chat
import wake_word
import web
from face_display import SodabotFace
from vision import FaceDetector, SFaceEmbedder

DB_RELOAD_SEC = 30  # register_face.py로 새로 등록된 얼굴을 주기적으로 반영


def _find_camera_index(name_substr, fallback):
    """USB 웹캠은 재연결될 때마다 /dev/videoN 번호가 바뀔 수 있어서,
    고정 인덱스 대신 장치 이름으로 찾는다."""
    for path in sorted(glob.glob("/sys/class/video4linux/video*/name")):
        try:
            with open(path) as f:
                dev_name = f.read().strip()
        except OSError:
            continue
        if name_substr in dev_name:
            return int(path.split("/")[-2].replace("video", ""))
    return fallback


def _read_frame_or_raise(cap, fail_count):
    ret, frame = cap.read()
    if ret:
        return frame, 0

    fail_count += 1
    if fail_count >= 60:
        raise RuntimeError("카메라에서 영상을 받지 못했습니다")
    return None, fail_count


def _capture_registration(cap, detector, embedder, name, app):
    """이미 열려 있는 카메라를 그대로 써서 얼굴 샘플을 여러 장 모아 등록한다
    (register_face.py와 같은 방식, 별도 카메라 핸들을 새로 열지 않음).
    사용자가 로봇 화면을 보고 준비할 수 있게 대기/카운트다운/진행상황을 캡션으로 안내한다."""
    fail_count = 0

    # 1) 얼굴이 잡힐 때까지 대기
    app.push_event(("caption", "{}님, 카메라를 봐주세요".format(name)))
    while True:
        frame, fail_count = _read_frame_or_raise(cap, fail_count)
        if frame is None:
            continue
        if detector.detect(frame):
            break

    # 2) 준비 카운트다운
    for n in (3, 2, 1):
        app.push_event(("caption", "{}초 뒤 촬영 시작...".format(n)))
        time.sleep(1)

    # 3) 버스트 촬영 (고개를 살짝씩 움직이며 여러 각도 확보)
    samples = []
    last_capture = 0
    last_frame = None

    while len(samples) < config.REGISTER_SAMPLES:
        frame, fail_count = _read_frame_or_raise(cap, fail_count)
        if frame is None:
            continue

        boxes = detector.detect(frame)
        if not boxes:
            continue

        x1, y1, x2, y2, score = boxes[0]
        margin = int((x2 - x1) * 0.15)
        x1c = max(0, x1 - margin)
        y1c = max(0, y1 - margin)
        x2c = min(frame.shape[1], x2 + margin)
        y2c = min(frame.shape[0], y2 + margin)
        face = frame[y1c:y2c, x1c:x2c]

        now = time.time()
        if now - last_capture >= config.REGISTER_CAPTURE_INTERVAL:
            samples.append(embedder.embed(face))
            last_capture = now
            last_frame = frame
            app.push_event((
                "caption",
                "촬영 중 {} / {} — 고개를 살짝씩 움직여주세요".format(
                    len(samples), config.REGISTER_SAMPLES
                ),
            ))

    final_embedding = np.mean(np.stack(samples), axis=0)
    path = face_db.save_person(name, final_embedding)

    _backup_photo(last_frame, name)

    app.push_event(("caption", "등록 완료: {}!".format(name)))
    time.sleep(2)
    app.push_event(("caption", ""))

    return path


def _backup_photo(frame, name):
    """등록 사진 한 장을 구글 드라이브(원생 사진 폴더)에 백업. 실패해도 등록 자체는 이미 끝난 뒤라 무시."""
    if frame is None or not os.path.exists(config.GDRIVE_KEY_PATH):
        return

    def _upload():
        jpg_path = tempfile.mktemp(suffix=".jpg")
        try:
            cv2.imwrite(jpg_path, frame)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            drive_upload.upload_photo(jpg_path, "{}_{}.jpg".format(name, stamp))
        except Exception as e:
            print("드라이브 업로드 실패:", e)
        finally:
            if os.path.exists(jpg_path):
                os.remove(jpg_path)

    threading.Thread(target=_upload, daemon=True).start()


def vision_loop(app, stop_event, conversation_active, register_queue):
    detector = FaceDetector()
    embedder = SFaceEmbedder()

    names, matrix = face_db.load_all()
    print("등록된 얼굴:", len(names), "명")

    camera_index = _find_camera_index("StreamCam", config.CAMERA_INDEX)
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
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
    last_face_time = time.time()  # sleepy 판단용: 마지막으로 얼굴이 보였던 시각
    face_was_present = False

    try:
        while not stop_event.is_set():
            try:
                name_to_reg, result, done = register_queue.get_nowait()
            except queue.Empty:
                pass
            else:
                app.push_event(("state", "thinking"))
                try:
                    result["path"] = _capture_registration(
                        cap, detector, embedder, name_to_reg, app
                    )
                    names, matrix = face_db.load_all()
                    app.push_event(("state", "happy"))
                except Exception as e:
                    result["error"] = str(e)
                    app.push_event(("state", "worried"))
                done.set()
                continue

            ret, frame = cap.read()
            if not ret:
                # 장치가 끊기는 등 계속 실패할 때 CPU를 100% 태우며 도는 걸 방지
                time.sleep(0.2)
                continue

            if conversation_active.is_set():
                # 대화 중엔 얼굴 인식(CPU 무거움)을 쉬어서 오디오 스트리밍에 CPU를 몰아준다.
                continue

            boxes = detector.detect(frame)
            now = time.time()

            if not boxes or (boxes[0][3] - boxes[0][1]) < config.MIN_FACE_SIZE:
                face_was_present = False
                if now - last_face_time >= config.SLEEPY_AFTER_SEC:
                    app.push_event(("sleepy",))
                else:
                    app.push_event(("idle",))
                continue

            last_face_time = now

            if not face_was_present:
                # 한동안 안 보이다가 방금 나타남
                face_was_present = True
                app.push_event(("surprised",))

            x1, y1, x2, y2, score = boxes[0]
            face = frame[y1:y2, x1:x2]
            embedding = embedder.embed(face)
            name, similarity = face_db.match_best(embedding, names, matrix)

            if name is not None and similarity >= config.MATCH_THRESHOLD:
                if now - last_greeted.get(name, 0) >= config.GREET_COOLDOWN_SEC:
                    last_greeted[name] = now
                    app.push_event(("greet", name))
                    print("인사:", name, round(similarity, 3))
            else:
                app.push_event(("curious",))

            if now - last_reload > DB_RELOAD_SEC:
                names, matrix = face_db.load_all()
                last_reload = now

    finally:
        cap.release()
        embedder.close()


def _on_trigger(app, conversation_active):
    if conversation_active.is_set():
        return  # 이미 대화 중이면 무시

    app.push_event(("wake",))
    conversation_active.set()
    try:
        voice_chat.start_conversation(on_state=lambda s: app.push_event(("state", s)))
    except Exception as e:
        print("대화 세션 오류:", e)
        app.push_event(("state", "worried"))
    finally:
        conversation_active.clear()


def main():
    proclock.stop_other(config.REGISTER_PID_FILE, "register_face.py")
    proclock.write_pid(config.MAIN_PID_FILE)

    app = SodabotFace()

    stop_event = threading.Event()
    conversation_active = threading.Event()
    register_queue = queue.Queue()
    worker = threading.Thread(
        target=vision_loop,
        args=(app, stop_event, conversation_active, register_queue),
        daemon=True,
    )
    worker.start()

    def trigger():
        threading.Thread(
            target=_on_trigger, args=(app, conversation_active), daemon=True
        ).start()

    def register(name):
        """웹 리모컨에서 호출. vision_loop가 카메라로 등록을 처리할 때까지 블로킹한다."""
        result = {}
        done = threading.Event()
        register_queue.put((name, result, done))
        if not done.wait(timeout=30):
            raise TimeoutError("등록 시간 초과")
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["path"]

    app.on_trigger = trigger  # 스페이스바 (즉시 확실하게 대화 시작)
    web.start_server(app, trigger, register, port=config.WEB_PORT)

    # 음성 웨이크워드("hi soda"). 자체 스레드에서 감지 대기하다가, 감지되면
    # _on_trigger를 직접(같은 스레드에서) 불러서 대화가 끝날 때까지 마이크를 넘겨준다.
    wake_thread = threading.Thread(
        target=wake_word.listen_for_wake_word,
        args=(lambda: _on_trigger(app, conversation_active),),
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
