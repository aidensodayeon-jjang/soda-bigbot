import sys

import config

if config.PYCUDA_PATH not in sys.path:
    sys.path.insert(0, config.PYCUDA_PATH)

import cv2
import numpy as np
import pycuda.driver as cuda
import tensorrt as trt


class FaceDetector:
    """OpenCV DNN 얼굴 검출기 (Res10 SSD, opencv/samples/dnn 공식 모델).
    Haar cascade보다 각도/조명 변화에 훨씬 강하고, OpenCV 4.1.1의 CPU dnn 모듈만으로 충분히 빠르다.
    """

    def __init__(
        self,
        prototxt=config.DETECTOR_PROTOTXT,
        model=config.DETECTOR_MODEL,
        confidence=config.DETECT_CONFIDENCE,
    ):
        self.net = cv2.dnn.readNetFromCaffe(prototxt, model)
        self.confidence = confidence

    def detect(self, frame):
        """[(x1, y1, x2, y2, score), ...] 를 큰 얼굴 순으로 반환."""
        h, w = frame.shape[:2]

        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)),
            1.0,
            (300, 300),
            (104.0, 177.0, 123.0),
        )

        self.net.setInput(blob)
        detections = self.net.forward()

        boxes = []

        for i in range(detections.shape[2]):
            score = float(detections[0, 0, i, 2])
            if score < self.confidence:
                continue

            x1 = int(detections[0, 0, i, 3] * w)
            y1 = int(detections[0, 0, i, 4] * h)
            x2 = int(detections[0, 0, i, 5] * w)
            y2 = int(detections[0, 0, i, 6] * h)

            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 <= x1 or y2 <= y1:
                continue

            boxes.append((x1, y1, x2, y2, score))

        boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)

        return boxes


class SFaceEmbedder:
    """SFace 얼굴 임베딩 (OpenCV Zoo 모델), be-more-agent에서 이미 빌드해 둔
    TensorRT 엔진(sface_fp16.engine)을 그대로 재사용한다. 128차원, L2 정규화된 벡터를 반환.
    pycuda 컨텍스트는 스레드에 종속되므로, 이 클래스는 반드시 그것을 사용하는
    스레드 한 곳에서만 생성/사용해야 한다.
    """

    def __init__(self, engine_path=config.SFACE_ENGINE):
        cuda.init()
        self.cuda_context = cuda.Device(0).make_context()

        logger = trt.Logger(trt.Logger.WARNING)

        with open(engine_path, "rb") as f:
            runtime = trt.Runtime(logger)
            self.engine = runtime.deserialize_cuda_engine(f.read())

        if self.engine is None:
            raise RuntimeError("TensorRT 엔진 로드 실패: " + engine_path)

        self.context = self.engine.create_execution_context()

        input_shape = tuple(self.engine.get_binding_shape(0))
        output_shape = tuple(self.engine.get_binding_shape(1))

        self.input_host = np.empty(input_shape, dtype=np.float32)
        self.output_host = np.empty(output_shape, dtype=np.float32)

        self.input_device = cuda.mem_alloc(self.input_host.nbytes)
        self.output_device = cuda.mem_alloc(self.output_host.nbytes)

        self.bindings = [int(self.input_device), int(self.output_device)]

    def embed(self, face_bgr):
        face = cv2.resize(face_bgr, (112, 112))
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        face = face.astype(np.float32)
        face = (face - 127.5) / 128.0
        face = np.transpose(face, (2, 0, 1))
        face = np.expand_dims(face, axis=0)
        face = np.ascontiguousarray(face, dtype=np.float32)

        np.copyto(self.input_host, face)
        cuda.memcpy_htod(self.input_device, self.input_host)

        if not self.context.execute_v2(self.bindings):
            raise RuntimeError("TensorRT 추론 실패")

        cuda.memcpy_dtoh(self.output_host, self.output_device)

        embedding = self.output_host.reshape(-1).copy()

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding /= norm

        return embedding

    def close(self):
        self.cuda_context.pop()
