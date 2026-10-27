"""Optional OpenCV SFace deep-learning duplicate enrollment screening.

Keeps the existing LBPH path available. This module never automatically
approves registration: uncertain/incomplete model data should be reviewed.
"""
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
DETECT = MODELS / "face_detection_yunet_2023mar.onnx"
RECOGNIZE = MODELS / "face_recognition_sface_2021dec.onnx"
# Conservative candidate threshold; tune against consented real-world samples.
SIMILARITY_FLAG = 0.36


def installed():
    return DETECT.is_file() and RECOGNIZE.is_file()


class DeepFaceVerifier:
    def __init__(self):
        if not installed():
            raise RuntimeError("Deep model files missing. See README setup.")
        self.detector = cv2.FaceDetectorYN.create(str(DETECT), "", (320, 320))
        self.recognizer = cv2.FaceRecognizerSF.create(str(RECOGNIZE), "")
        self.gallery = {}

    def embed(self, frame):
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        # The 2023mar YuNet ONNX file expects fixed 320 x 320 input.
        view = cv2.resize(frame, (320, 320))
        self.detector.setInputSize((320, 320))
        _, faces = self.detector.detect(view)
        if faces is None or len(faces) != 1:
            return None
        aligned = self.recognizer.alignCrop(view, faces[0])
        vector = self.recognizer.feature(aligned).flatten().astype(np.float32)
        norm = np.linalg.norm(vector)
        if norm < 1e-8:
            return None
        return vector / norm

    def build_gallery(self, faces_root, students):
        self.gallery.clear()
        for sid in students:
            vectors = []
            for path in sorted((faces_root / str(sid)).glob("*.png")):
                img = cv2.imread(str(path))
                if img is None:
                    continue
                feature = self.embed(img)
                if feature is not None:
                    vectors.append(feature)
            if vectors:
                self.gallery[sid] = vectors
        return self.gallery

    def potential_match(self, frames, students):
        """Return possible match (ID, name, similarity) or None, never auto-enroll."""
        best = None
        for frame in frames:
            sample = self.embed(frame)
            if sample is None:
                continue
            for sid, vectors in self.gallery.items():
                score = max(float(np.dot(sample, reference)) for reference in vectors)
                if score >= SIMILARITY_FLAG and (best is None or score > best[2]):
                    best = (sid, students[sid], score)
        return best
