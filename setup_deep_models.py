"""Download optional official OpenCV Zoo ONNX models. Requires internet."""
from pathlib import Path
from urllib.request import Request, urlopen
import shutil

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
FILES = {
    "face_detection_yunet_2023mar.onnx":
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx":
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def main():
    MODELS.mkdir(exist_ok=True)
    for filename, url in FILES.items():
        target = MODELS / filename
        if target.exists() and target.stat().st_size > 100_000:
            print(f"Already installed: {filename}")
            continue
        temporary = target.with_suffix(".download")
        try:
            request = Request(url, headers={"User-Agent": "FaceAttendanceProject/1.0"})
            print(f"Downloading {filename}...")
            with urlopen(request, timeout=90) as response, temporary.open("wb") as out:
                shutil.copyfileobj(response, out)
            if temporary.stat().st_size < 100_000:
                raise RuntimeError("File is too small to be an ONNX model.")
            temporary.replace(target)
            print(f"Installed {filename} ({target.stat().st_size:,} bytes)")
        finally:
            temporary.unlink(missing_ok=True)
    print("Deep face comparison models are ready.")


if __name__ == "__main__":
    main()
