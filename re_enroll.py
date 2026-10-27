"""Re-enroll an existing student without changing student ID or attendance records."""
import argparse
import shutil
import sqlite3
import tempfile
from pathlib import Path
import cv2
from main import DB, FACES, FACES_FULL, MODEL, camera, detector, crop_faces, train

STAGES = [("FRONT", 0), ("LEFT", 1), ("RIGHT", 2)]
PER_STAGE = 12


def re_enroll(student_id):
    with sqlite3.connect(DB) as con:
        row = con.execute("SELECT name FROM students WHERE id=?", (student_id,)).fetchone()
    if row is None:
        raise RuntimeError("Student ID not found.")
    cascade = detector()
    cam = camera()
    with tempfile.TemporaryDirectory(prefix="face_reenroll_", dir=ROOT) as workspace:
        root = Path(workspace)
        crop_dir, full_dir = root / "crop", root / "full"
        crop_dir.mkdir()
        full_dir.mkdir()
        current = 0
        count = 0
        ticks = 0
        print(f"Re-enrolling {row[0]} (ID {student_id}). Q cancels. Follow the angle prompts.")
        try:
            while current < len(STAGES):
                ok, frame = cam.read()
                if not ok:
                    raise RuntimeError("Camera disconnected; existing face data unchanged.")
                title, _ = STAGES[current]
                original_frame = frame.copy()
                gray, boxes = crop_faces(frame, cascade)
                if len(boxes) == 1:
                    x, y, w, h = boxes[0]
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 220, 160), 2)
                    ticks += 1
                    if ticks % 5 == 0:
                        number = current * PER_STAGE + count
                        cv2.imwrite(str(crop_dir / f"{number:03d}.png"),
                                    cv2.resize(gray[y:y+h, x:x+w], (200, 200)))
                        cv2.imwrite(str(full_dir / f"{number:03d}.jpg"), original_frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, 90])
                        count += 1
                        if count == PER_STAGE:
                            current += 1
                            count = 0
                            ticks = 0
                cv2.putText(frame, f"Look {title} - {count}/{PER_STAGE}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2)
                cv2.putText(frame, f"Total {current*PER_STAGE+count}/36 | Q cancel",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
                cv2.imshow("Guided Face Re-Enrollment", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    raise RuntimeError("Cancelled; original face samples were kept.")
        finally:
            cam.release()
            cv2.destroyAllWindows()

        # Stage replacement and roll back if training fails; database is never modified.
        old_crop = FACES / str(student_id)
        old_full = FACES_FULL / str(student_id)
        backup_crop, backup_full = root / "old_crop", root / "old_full"
        if old_crop.exists():
            old_crop.rename(backup_crop)
        if old_full.exists():
            old_full.rename(backup_full)
        old_model = root / "old_model.yml"
        if MODEL.exists():
            shutil.copy2(MODEL, old_model)
        try:
            FACES.mkdir(exist_ok=True)
            FACES_FULL.mkdir(exist_ok=True)
            shutil.copytree(crop_dir, old_crop)
            shutil.copytree(full_dir, old_full)
            train()
        except Exception:
            shutil.rmtree(old_crop, ignore_errors=True)
            shutil.rmtree(old_full, ignore_errors=True)
            if backup_crop.exists():
                backup_crop.rename(old_crop)
            if backup_full.exists():
                backup_full.rename(old_full)
            if old_model.exists():
                shutil.copy2(old_model, MODEL)
            else:
                MODEL.unlink(missing_ok=True)
            raise
        print(f"SUCCESS: {row[0]} (ID {student_id}) face samples updated; attendance preserved.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--id", type=int, required=True)
    args = p.parse_args()
    try:
        re_enroll(args.id)
    except (RuntimeError, OSError, cv2.error) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
