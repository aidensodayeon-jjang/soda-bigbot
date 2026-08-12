import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import voice_chat
from face_display import KEY_STATES

INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>소다봇 리모컨</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="소다봇">
<link rel="apple-touch-icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%23000'/%3E%3Ctext x='50' y='66' font-size='56' text-anchor='middle'%3E%F0%9F%A5%A4%3C/text%3E%3C/svg%3E">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext x='50' y='72' font-size='72' text-anchor='middle'%3E%F0%9F%A5%A4%3C/text%3E%3C/svg%3E">
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0b0b0f; color: #fff;
         margin: 0; padding: calc(24px + env(safe-area-inset-top)) 16px
         calc(60px + env(safe-area-inset-bottom)); }}
  h1 {{ font-size: 20px; margin: 0 0 20px; }}
  h2 {{ font-size: 14px; color: #9aa; margin: 28px 0 10px; }}
  button {{ font-size: 16px; padding: 14px; border: none; border-radius: 12px;
            background: #20D9FF; color: #000; font-weight: 600; }}
  button:active {{ background: #0fb8dd; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }}
  .big {{ width: 100%; padding: 18px; font-size: 18px; margin-bottom: 8px; }}
  input[type=text] {{ width: 100%; box-sizing: border-box; padding: 14px; font-size: 16px;
                       border-radius: 12px; border: 1px solid #444; margin-bottom: 10px;
                       background: #1a1a20; color: #fff; }}
  #status {{ color: #9aa; font-size: 13px; margin-top: 16px; min-height: 18px; }}
</style>
</head>
<body>
  <h1>🥤 소다봇 리모컨</h1>

  <button class="big" onclick="trigger()">🎙️ 대화 시작</button>

  <h2>표정</h2>
  <div class="grid">
    {expression_buttons}
  </div>

  <h2>말하기</h2>
  <input type="text" id="sayText" placeholder="소다봇이 말할 문장">
  <button class="big" onclick="say()">🔊 말하기</button>

  <button class="big" onclick="post('/toggle_character')">🖼️ 캐릭터 그림 ↔ 원래 도형</button>

  <h2>얼굴 등록</h2>
  <input type="text" id="regName" placeholder="이름">
  <button class="big" onclick="register()">📸 얼굴 등록 (카메라를 봐주세요)</button>

  <div id="status"></div>

<script>
function setStatus(msg) {{
  document.getElementById('status').textContent = msg;
}}
function post(path, body) {{
  setStatus('전송 중...');
  return fetch(path, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: body ? JSON.stringify(body) : undefined,
  }})
    .then(r => r.text().then(text => {{
      setStatus(r.ok ? '완료' : '오류: ' + text);
    }}))
    .catch(e => setStatus('오류: ' + e));
}}
function trigger() {{ post('/trigger'); }}
function setExpression(name) {{ post('/expression', {{state: name}}); }}
function say() {{
  const text = document.getElementById('sayText').value.trim();
  if (!text) return;
  post('/say', {{text: text}});
}}
function register() {{
  const name = document.getElementById('regName').value.trim();
  if (!name) return;
  setStatus('등록 중... 로봇 카메라를 봐주세요 (몇 초 소요)');
  post('/register', {{name: name}});
}}
</script>
</body>
</html>
"""

_STATE_LABELS = {
    "idle": "기본", "happy": "행복", "surprised": "놀람", "thinking": "생각",
    "sleepy": "졸림", "speaking": "말함", "curious": "궁금", "excited": "신남",
    "worried": "걱정",
}


def _render_index():
    buttons = "\n".join(
        '<button onclick="setExpression(\'{0}\')">{1}</button>'.format(
            name, _STATE_LABELS.get(name, name)
        )
        for name in KEY_STATES
    )
    return INDEX_HTML.format(expression_buttons=buttons).encode("utf-8")


def _make_handler(hooks):
    index_body = _render_index()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # 콘솔 스팸 방지

        def _send(self, status, body, content_type="text/plain; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length))

        def do_GET(self):
            if self.path == "/":
                self._send(200, index_body, "text/html; charset=utf-8")
            else:
                self._send(404, b"not found")

        def do_POST(self):
            try:
                if self.path == "/trigger":
                    hooks["trigger"]()
                    self._send(200, b"ok")
                elif self.path == "/expression":
                    data = self._read_json()
                    hooks["set_state"](data["state"])
                    self._send(200, b"ok")
                elif self.path == "/say":
                    data = self._read_json()
                    hooks["say"](data["text"])
                    self._send(200, b"ok")
                elif self.path == "/toggle_character":
                    hooks["toggle_character"]()
                    self._send(200, b"ok")
                elif self.path == "/register":
                    data = self._read_json()
                    hooks["register"](data["name"])
                    self._send(200, b"ok")
                else:
                    self._send(404, b"not found")
            except Exception as e:
                self._send(500, str(e).encode("utf-8"))

    return Handler


def _self_check():
    html = _render_index().decode("utf-8")
    for name in KEY_STATES:
        assert "setExpression('{}')".format(name) in html


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True  # 재시작 직후 TIME_WAIT로 포트 충돌하는 것 방지


def start_server(app, trigger, register, port=8080):
    """main.py에서 호출. 모바일 웹 리모컨을 백그라운드 스레드로 띄운다.
    /register는 몇 초씩 블로킹되므로 요청마다 스레드를 띄우는 서버를 쓴다."""
    hooks = {
        "trigger": trigger,
        "set_state": lambda name: app.push_event(("state", name)),
        "say": lambda text: threading.Thread(
            target=voice_chat.speak, args=(text,), daemon=True
        ).start(),
        "register": register,
        "toggle_character": lambda: app.push_event(("toggle_character",)),
    }
    server = _ThreadingHTTPServer(("0.0.0.0", port), _make_handler(hooks))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("웹 리모컨: http://<젯슨 IP>:{}".format(port))
    return server
