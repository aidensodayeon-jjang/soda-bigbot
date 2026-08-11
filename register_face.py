import os
import sys
import time

if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np

import config
import face_db
import proclock
from vision import FaceDetector, SFaceEmbedder

WINDOW = "SODABOT Register"
DISPLAY_W, DISPLAY_H = 800, 480

# 카메라가 다른 프로그램(main.py 등)에 잡혀있으면 read()가 계속 실패한다.
# 화면이 멈춘 것처럼 보이지 않도록 일정 횟수 이상 실패하면 바로 에러로 종료한다.
MAX_READ_FAILURES = 60


def read_frame(cap, fail_count):
    ret, frame = cap.read()
    if ret:
        return frame, 0

    fail_count += 1
    if fail_count >= MAX_READ_FAILURES:
        cv2.destroyAllWindows()
        sys.exit(
            "카메라에서 영상을 받지 못했습니다. "
            "main.py 등 카메라를 쓰는 다른 프로그램이 켜져 있으면 먼저 종료하세요."
        )

    return None, fail_count


def fullscreen_window():
    cv2.namedWindow(WINDOW, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


def to_display(frame):
    return cv2.resize(frame, (DISPLAY_W, DISPLAY_H))


def scale_box(box, frame_shape):
    x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
    fh, fw = frame_shape[:2]
    sx = DISPLAY_W / fw
    sy = DISPLAY_H / fh
    return int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)


def put_center_text(disp, text, y, scale=1.0, color=(255, 255, 255), thickness=2):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    x = (DISPLAY_W - tw) // 2
    cv2.putText(disp, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)


def wait_for_face(cap, detector, name):
    """얼굴이 잡힐 때까지 카메라 화면을 보여주며 대기."""
    fail_count = 0

    while True:
        frame, fail_count = read_frame(cap, fail_count)
        if frame is None:
            continue

        boxes = detector.detect(frame)
        disp = to_display(frame)

        put_center_text(disp, name, 45, 1.0, (255, 255, 255), 2)

        if boxes:
            x1, y1, x2, y2 = scale_box(boxes[0], frame.shape)
            cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 3)
            put_center_text(disp, "얼굴을 찾았습니다", DISPLAY_H - 40, 0.9, (0, 255, 0), 2)
            cv2.imshow(WINDOW, disp)
            cv2.waitKey(500)
            return

        put_center_text(disp, "카메라를 봐주세요", DISPLAY_H - 40, 0.9, (0, 200, 255), 2)
        cv2.imshow(WINDOW, disp)
        cv2.waitKey(1)


def countdown(cap):
    fail_count = 0

    for n in (3, 2, 1):
        end = time.time() + 1.0
        while time.time() < end:
            frame, fail_count = read_frame(cap, fail_count)
            if frame is None:
                continue

            disp = to_display(frame)
            put_center_text(disp, str(n), DISPLAY_H // 2 + 30, 4.0, (0, 255, 255), 8)
            cv2.imshow(WINDOW, disp)
            cv2.waitKey(1)


def capture_burst(cap, detector, embedder):
    samples = []
    last_capture = 0
    flash_until = 0
    fail_count = 0

    while len(samples) < config.REGISTER_SAMPLES:
        frame, fail_count = read_frame(cap, fail_count)
        if frame is None:
            continue

        boxes = detector.detect(frame)
        disp = to_display(frame)

        if boxes:
            x1, y1, x2, y2, score = boxes[0]

            margin = int((x2 - x1) * 0.15)
            x1c = max(0, x1 - margin)
            y1c = max(0, y1 - margin)
            x2c = min(frame.shape[1], x2 + margin)
            y2c = min(frame.shape[0], y2 + margin)

            face = frame[y1c:y2c, x1c:x2c]

            dx1, dy1, dx2, dy2 = scale_box((x1, y1, x2, y2), frame.shape)
            cv2.rectangle(disp, (dx1, dy1), (dx2, dy2), (0, 255, 0), 3)

            now = time.time()
            if now - last_capture >= config.REGISTER_CAPTURE_INTERVAL:
                embedding = embedder.embed(face)
                samples.append(embedding)
                last_capture = now
                flash_until = now + 0.15
                print("촬영: {} / {}".format(len(samples), config.REGISTER_SAMPLES))

        if time.time() < flash_until:
            overlay = disp.copy()
            cv2.rectangle(overlay, (0, 0), (DISPLAY_W, DISPLAY_H), (255, 255, 255), -1)
            disp = cv2.addWeighted(overlay, 0.5, disp, 0.5, 0)

        put_center_text(
            disp, "{} / {}".format(len(samples), config.REGISTER_SAMPLES),
            55, 1.3, (0, 255, 0), 3,
        )
        put_center_text(disp, "고개를 살짝씩 움직여주세요", DISPLAY_H - 30, 0.8, (255, 255, 255), 2)

        cv2.imshow(WINDOW, disp)
        cv2.waitKey(1)

    return samples


def show_done(cap, name):
    end_time = time.time() + 2
    while time.time() < end_time:
        ret, frame = cap.read()
        if not ret:
            break

        disp = to_display(frame)
        put_center_text(disp, "등록 완료!", DISPLAY_H // 2 - 20, 1.6, (0, 255, 0), 4)
        put_center_text(disp, name, DISPLAY_H // 2 + 40, 1.2, (0, 255, 0), 3)

        cv2.imshow(WINDOW, disp)
        cv2.waitKey(1)


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 register_face.py <이름>")
        sys.exit(1)

    name = sys.argv[1]

    proclock.stop_other(config.MAIN_PID_FILE, "main.py")
    proclock.write_pid(config.REGISTER_PID_FILE)

    detector = FaceDetector()
    embedder = SFaceEmbedder()

    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.REGISTER_CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.REGISTER_CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("카메라 열기 실패")
        embedder.close()
        proclock.remove_pid(config.REGISTER_PID_FILE)
        sys.exit(1)

    fullscreen_window()

    print("=" * 30)
    print("SODABOT 얼굴 등록:", name)
    print("=" * 30)

    try:
        wait_for_face(cap, detector, name)
        countdown(cap)
        samples = capture_burst(cap, detector, embedder)

        final_embedding = np.mean(np.stack(samples), axis=0)
        path = face_db.save_person(name, final_embedding)

        print("=" * 30)
        print("등록 완료:", name)
        print("샘플 수:", len(samples))
        print("저장 위치:", path)
        print("=" * 30)

        show_done(cap, name)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        embedder.close()
        proclock.remove_pid(config.REGISTER_PID_FILE)


if __name__ == "__main__":
    main()
