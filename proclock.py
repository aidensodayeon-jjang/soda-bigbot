import os
import signal
import time

"""main.py와 register_face.py는 카메라와 GPU(TensorRT)를 동시에 쓸 수 없어서
(둘 다 실행하면 화면이 가려지는 정도가 아니라 프로세스가 멈춘다), 서로 시작할 때
상대방을 종료시켜야 한다. 이때 `pgrep -f`로 명령행 문자열을 검색하면 우연히
같은 글자("main.py" 등)를 포함한 무관한 프로세스까지 잘못 죽일 수 있으므로,
반드시 이 PID 파일 방식처럼 각 프로세스가 자기 PID를 직접 기록/확인하게 한다.
"""


def write_pid(path):
    with open(path, "w") as f:
        f.write(str(os.getpid()))


def remove_pid(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_other(pid_file, label):
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return

    if pid == os.getpid() or not _alive(pid):
        return

    print("카메라/GPU를 쓰고 있는 {}(pid {})를 먼저 종료합니다.".format(label, pid))

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return

    for _ in range(20):
        if not _alive(pid):
            break
        time.sleep(0.1)

    if _alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        time.sleep(0.5)
