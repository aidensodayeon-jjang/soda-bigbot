import os
import queue
import random
import tkinter as tk

if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

import config

# =========================================================
# SODABOT FACE (be-more-agent/face2.py 디자인을 그대로 재사용)
# 800 x 480, 둥근 사각형 눈
# =========================================================

W = 800
H = 480

BG = "#000000"
CYAN = "#20D9FF"
WHITE = "#FFFFFF"

LEFT_X = 285
RIGHT_X = 515
EYE_Y = 205

EYE_W = 92
EYE_H = 118
EYE_RADIUS = 28

MOUTH_Y = 345

NO_BLINK_STATES = ("happy", "sleepy", "excited")
KEY_STATES = [
    "idle", "happy", "surprised", "thinking",
    "sleepy", "speaking", "curious", "excited", "worried",
]


class SodabotFace:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SODABOT FACE")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=BG)

        self.canvas = tk.Canvas(
            self.root, width=W, height=H, bg=BG, highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.state = "idle"
        self.blink = False
        self.speaking_open = False
        self.eye_dx = 0
        self.eye_dy = 0
        self.caption = ""

        self.events = queue.Queue()
        self.on_trigger = lambda: None  # main.py가 채워 넣는 대화 시작 콜백

        # 상태별 캐릭터 그림이 있으면 도형 대신 그걸 쓴다 (지금은 idle만 준비됨).
        self.character_images = {}
        for key in ("idle_open", "idle_blink"):
            path = os.path.join(config.CHARACTER_DIR, key + ".png")
            if os.path.exists(path):
                self.character_images[key] = tk.PhotoImage(file=path)

        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<space>", lambda e: self.on_trigger())
        for i, name in enumerate(KEY_STATES, start=1):
            self.root.bind(str(i), lambda e, n=name: self.set_state(n))

        self._draw()
        self._schedule_blink()
        self._move_eyes()
        self._animate_speaking()
        self._poll_events()

    # -----------------------------------------------------
    # 외부(비전 스레드)에서 호출하는 스레드 안전 API
    # -----------------------------------------------------

    def push_event(self, event):
        self.events.put(event)

    def _poll_events(self):
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass

        self.root.after(100, self._poll_events)

    def _handle_event(self, event):
        kind = event[0]

        if kind == "greet":
            name = event[1]
            self.set_state("happy")
            self.show_caption(
                "안녕하세요, {}님!".format(name), config.GREETING_DURATION_MS
            )
            self.root.after(
                config.GREETING_DURATION_MS, lambda: self._end_greeting("happy")
            )

        elif kind == "curious":
            if self.state == "idle":
                self.set_state("curious")

        elif kind == "idle":
            if self.state == "curious":
                self.set_state("idle")

        elif kind == "surprised":
            # 한동안 안 보이다가 갑자기 얼굴이 나타난 순간(=방금 알아챔)
            self.set_state("surprised")
            self.root.after(1000, lambda: self._end_greeting("surprised"))

        elif kind == "sleepy":
            if self.state == "idle":
                self.set_state("sleepy")

        elif kind == "wake":
            self.set_state("excited")
            self.show_caption("네, 불렀어요?", config.GREETING_DURATION_MS)
            self.root.after(
                config.GREETING_DURATION_MS, lambda: self._end_greeting("excited")
            )

        elif kind == "state":
            value = event[1]
            self.set_state(value)
            if value == "worried":
                self.root.after(2000, lambda: self._end_greeting("worried"))

        elif kind == "caption":
            # show_caption과 달리 자동으로 안 지워짐 (등록 진행 상황처럼 빠르게
            # 계속 갱신되는 안내문에 사용. 빈 문자열을 보내면 지운다).
            self.caption = event[1]
            self._draw()

    def _end_greeting(self, expected_state):
        if self.state == expected_state:
            self.set_state("idle")

    def run(self):
        self.root.mainloop()

    # -----------------------------------------------------
    # 상태 / 자막
    # -----------------------------------------------------

    def set_state(self, new_state):
        self.state = new_state
        self.blink = False
        self.eye_dx = 0
        self.eye_dy = 0
        self._draw()

    def show_caption(self, text, duration_ms=4000):
        self.caption = text
        self._draw()
        self.root.after(duration_ms, self._clear_caption)

    def _clear_caption(self, text=None):
        # 그사이 다른 자막으로 바뀌었으면 지우지 않음
        if text is None or self.caption == text:
            self.caption = ""
            self._draw()

    # -----------------------------------------------------
    # 그리기 헬퍼
    # -----------------------------------------------------

    def _clear(self):
        self.canvas.delete("all")

    def _rounded_rect(self, x1, y1, x2, y2, radius, fill):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        self.canvas.create_polygon(
            points, smooth=True, splinesteps=36, fill=fill, outline=""
        )

    def _rounded_eye(self, x, y, w=EYE_W, h=EYE_H, radius=EYE_RADIUS):
        self._rounded_rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, radius, CYAN)

    # -- 눈 --

    def _normal_eye(self, x, y):
        self._rounded_eye(x + self.eye_dx, y + self.eye_dy)

    def _small_eye(self, x, y):
        self._rounded_eye(x, y, 65, 78, 22)

    def _large_eye(self, x, y):
        self._rounded_eye(x, y, 104, 132, 32)

    def _closed_eye(self, x, y):
        self._rounded_rect(x - 52, y - 7, x + 52, y + 7, 7, CYAN)

    def _sleepy_eye(self, x, y):
        self._rounded_rect(x - 52, y - 8, x + 52, y + 8, 8, CYAN)

    def _happy_eye(self, x, y):
        self.canvas.create_arc(
            x - 58, y - 20, x + 58, y + 72,
            start=25, extent=130, style="arc", outline=CYAN, width=18,
        )

    def _worried_eye(self, x, y, left=True):
        self._rounded_eye(x, y, 88, 108, 26)

        if left:
            self.canvas.create_polygon(
                x - 65, y - 75, x + 65, y - 75,
                x + 65, y - 48, x - 65, y - 72,
                fill=BG, outline="",
            )
        else:
            self.canvas.create_polygon(
                x - 65, y - 75, x + 65, y - 75,
                x + 65, y - 72, x - 65, y - 48,
                fill=BG, outline="",
            )

    # -- 입 --

    def _mouth_idle(self):
        self._rounded_rect(376, MOUTH_Y - 5, 408, MOUTH_Y + 5, 5, CYAN)
        self.canvas.create_oval(416, MOUTH_Y - 7, 430, MOUTH_Y + 7, fill=CYAN, outline="")

    def _mouth_dot(self):
        self.canvas.create_oval(392, MOUTH_Y - 9, 408, MOUTH_Y + 7, fill=CYAN, outline="")

    def _mouth_open(self):
        self._rounded_rect(378, MOUTH_Y - 14, 422, MOUTH_Y + 14, 13, CYAN)

    def _mouth_surprise(self):
        self.canvas.create_oval(
            383, MOUTH_Y - 19, 417, MOUTH_Y + 15, outline=CYAN, width=9
        )

    def _mouth_sad(self):
        self.canvas.create_arc(
            368, MOUTH_Y - 3, 432, MOUTH_Y + 48,
            start=20, extent=140, style="arc", outline=CYAN, width=9,
        )

    def _mouth_big_happy(self):
        self.canvas.create_arc(
            365, MOUTH_Y - 30, 435, MOUTH_Y + 38,
            start=180, extent=180, style="pieslice", fill=CYAN, outline=CYAN,
        )
        self.canvas.create_rectangle(
            355, MOUTH_Y - 40, 445, MOUTH_Y - 2, fill=BG, outline=""
        )

    # -----------------------------------------------------
    # 표정 (1~9 키와 동일)
    # -----------------------------------------------------

    def _draw_idle(self):
        self._normal_eye(LEFT_X, EYE_Y)
        self._normal_eye(RIGHT_X, EYE_Y)
        self._mouth_idle()

    def _draw_happy(self):
        self._happy_eye(LEFT_X, EYE_Y)
        self._happy_eye(RIGHT_X, EYE_Y)
        self._mouth_big_happy()

    def _draw_surprised(self):
        self._large_eye(LEFT_X, EYE_Y)
        self._large_eye(RIGHT_X, EYE_Y)
        self._mouth_surprise()

    def _draw_thinking(self):
        self._small_eye(LEFT_X, EYE_Y + 8)
        self._rounded_eye(RIGHT_X, EYE_Y - 5, 96, 116, 28)
        self._mouth_idle()

    def _draw_sleepy(self):
        self._sleepy_eye(LEFT_X, EYE_Y)
        self._sleepy_eye(RIGHT_X, EYE_Y)
        self._mouth_idle()
        self.canvas.create_text(625, 105, text="Z", fill=CYAN, font=("Arial", 32, "bold"))
        self.canvas.create_text(662, 78, text="z", fill=CYAN, font=("Arial", 24, "bold"))

    def _draw_speaking(self):
        self._rounded_eye(LEFT_X, EYE_Y, 82, 105, 25)
        self._rounded_eye(RIGHT_X, EYE_Y, 82, 105, 25)
        if self.speaking_open:
            self._mouth_open()
        else:
            self._mouth_dot()

    def _draw_curious(self):
        self._small_eye(LEFT_X, EYE_Y + 5)
        self._large_eye(RIGHT_X, EYE_Y - 8)
        self._mouth_dot()
        self.canvas.create_text(640, 105, text="?", fill=CYAN, font=("Arial", 50, "bold"))

    def _draw_excited(self):
        self._happy_eye(LEFT_X, EYE_Y)
        self._happy_eye(RIGHT_X, EYE_Y)
        self._mouth_big_happy()

    def _draw_worried(self):
        self._worried_eye(LEFT_X, EYE_Y, True)
        self._worried_eye(RIGHT_X, EYE_Y, False)
        self._mouth_sad()

    def _draw_idle_image(self):
        key = "idle_blink" if self.blink else "idle_open"
        self.canvas.create_image(W / 2, H / 2, image=self.character_images[key])

    def _draw(self):
        self._clear()

        if self.state == "idle" and "idle_open" in self.character_images:
            self._draw_idle_image()
            self._draw_caption()
            return

        if self.blink and self.state not in NO_BLINK_STATES:
            self._closed_eye(LEFT_X, EYE_Y)
            self._closed_eye(RIGHT_X, EYE_Y)
            self._mouth_idle()
            self._draw_caption()
            return

        draw_fn = {
            "idle": self._draw_idle,
            "happy": self._draw_happy,
            "surprised": self._draw_surprised,
            "thinking": self._draw_thinking,
            "sleepy": self._draw_sleepy,
            "speaking": self._draw_speaking,
            "curious": self._draw_curious,
            "excited": self._draw_excited,
            "worried": self._draw_worried,
        }.get(self.state, self._draw_idle)

        draw_fn()
        self._draw_caption()

    def _draw_caption(self):
        if not self.caption:
            return

        self.canvas.create_text(
            W / 2, H - 35,
            text=self.caption,
            fill=WHITE,
            font=("Noto Sans CJK KR", 26, "bold"),
            width=W - 60,
        )

    # -----------------------------------------------------
    # 애니메이션 루프
    # -----------------------------------------------------

    def _blink_start(self):
        if self.state not in NO_BLINK_STATES:
            self.blink = True
            self._draw()
            self.root.after(130, self._blink_end)
        else:
            self._schedule_blink()

    def _blink_end(self):
        self.blink = False
        self._draw()
        self._schedule_blink()

    def _schedule_blink(self):
        self.root.after(random.randint(2600, 5500), self._blink_start)

    def _move_eyes(self):
        if self.state == "idle":
            self.eye_dx = random.randint(-7, 7)
            self.eye_dy = random.randint(-4, 4)
            self._draw()

        self.root.after(random.randint(1700, 3200), self._move_eyes)

    def _animate_speaking(self):
        if self.state == "speaking":
            self.speaking_open = not self.speaking_open
            self._draw()

        self.root.after(220, self._animate_speaking)


if __name__ == "__main__":
    # 단독 실행 시: 표정 미리보기 (1~9 키, ESC 종료)
    SodabotFace().run()
