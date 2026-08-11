import glob
import os

import numpy as np

import config

EMBED_DIM = 128


def load_all():
    """faces/ 안의 *.npy를 모두 읽어 (이름 목록, 정규화된 임베딩 행렬)로 반환.
    등록 인원이 늘어도(최대 수백 명) 매칭은 행렬곱 한 번이라 비용이 거의 없다.
    """
    os.makedirs(config.FACES_DIR, exist_ok=True)

    names = []
    vectors = []

    for path in sorted(glob.glob(os.path.join(config.FACES_DIR, "*.npy"))):
        name = os.path.splitext(os.path.basename(path))[0]
        embedding = np.load(path).astype(np.float32)

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        names.append(name)
        vectors.append(embedding)

    if vectors:
        matrix = np.stack(vectors)
    else:
        matrix = np.zeros((0, EMBED_DIM), dtype=np.float32)

    return names, matrix


def save_person(name, embedding):
    os.makedirs(config.FACES_DIR, exist_ok=True)

    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    path = os.path.join(config.FACES_DIR, name + ".npy")
    np.save(path, embedding.astype(np.float32))

    return path


def match_best(embedding, names, matrix):
    """코사인 유사도로 가장 가까운 (이름, 점수)를 반환. DB가 비어있으면 (None, 0.0)."""
    if len(names) == 0:
        return None, 0.0

    scores = matrix @ embedding
    idx = int(np.argmax(scores))

    return names[idx], float(scores[idx])
