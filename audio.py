import glob
import os
import random
import subprocess


def pick_random(directory):
    files = glob.glob(os.path.join(directory, "*.wav"))
    return random.choice(files) if files else None


def play(path):
    """aplay로 비동기 재생 (인식 루프를 막지 않음)."""
    if not path or not os.path.exists(path):
        return

    subprocess.Popen(
        ["aplay", "-q", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
