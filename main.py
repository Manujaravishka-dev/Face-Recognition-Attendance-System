import argparse
import csv
import sqlite3
import sys
from urllib.request import urlretrieve
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
FACES = ROOT / 'faces'
MODEL = ROOT / 'model.yml'
DB = ROOT / 'attendance.db'
FACES.mkdir(exist_ok=True)


def connect():
    con = sqlite3.connect(DB)
    con.execute('CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
    con.execute('''CREATE TABLE IF NOT EXISTS attendance (
        student_id INTEGER NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
        PRIMARY KEY(student_id, date), FOREIGN KEY(student_id) REFERENCES students(id))''')
    con.commit()
    return con


def detector():
    # OpenCV 5 distributions may not bundle the Haar cascade XML.
    cascade_file = ROOT / 'haarcascade_frontalface_default.xml'
    packaged_file = Path(cv2.data.haarcascades) / cascade_file.name
    if not cascade_file.exists() and packaged_file.exists():
        cascade_file = packaged_file
    if not cascade_file.exists():
        url = ('https://raw.githubusercontent.com/opencv/opencv/'
               '4.10.0/data/haarcascades/haarcascade_frontalface_default.xml')
        print('Face detector XML not found. Downloading official OpenCV cascade...')
        try:
            urlretrieve(url, cascade_file)
        except Exception as exc:
            raise RuntimeError(
                'Cannot download face detector. Check internet connection and retry.'
            ) from exc
    cascade = cv2.CascadeClassifier(str(cascade_file))
    if cascade.empty():
        raise RuntimeError('Could not load face detector XML; delete the XML and retry.')
    return cascade

def camera():
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        raise RuntimeError('Cannot open webcam. Check permissions and other camera apps.')
    return cam


def crop_faces(frame, cascade):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    boxes = cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(90, 90))
    return gray, boxes



class DuplicateFaceError(RuntimeError):
    """Potential match with an existing student; prevent automatic registration."""


def existing_face_samples():
    """Use actual enrolled images, not only a potentially stale trained model."""
    with connect() as con:
        people = dict(con.execute('SELECT id, name FROM students').fetchall())
    images, labels = [], []
    for sid in people:
        folder = FACES / str(sid)
        if not folder.is_dir():
            raise RuntimeError(f'Missing enrolled face photos for student {sid}. Manual review required.')
        loaded = 0
        for path in sorted(folder.glob('*.png')):
            face = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if face is not None:
                images.append(cv2.resize(face, (200, 200)))
                labels.append(sid)
                loaded += 1
        if loaded < 10:
            raise RuntimeError(f'Insufficient existing face samples for ID {sid}. Manual review required.')
    return people, images, labels


def duplicate_evidence(candidates, people, images, labels):
    """Conservative alert: repeated close matches require a human to resolve."""
    if not people:
        return None
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(images, np.asarray(labels, dtype=np.int32))
    votes = {}
    for face in candidates:
        sid, distance = recognizer.predict(face)
        if sid in people and distance < 65:
            votes[sid] = votes.get(sid, 0) + 1
    minimum = max(2, len(candidates) // 4)
    for sid, count in sorted(votes.items(), key=lambda item: -item[1]):
        if count >= minimum:
            return sid, people[sid], count
    return None


def check_existing_face(cam, cascade):
    """Fail closed: compare every candidate to enrolled samples before registration."""
    people, images, labels = existing_face_samples()
    if not people:
        return
    candidates = []
    frames = 0
    while len(candidates) < 24 and frames < 400:
        ok, frame = cam.read()
        if not ok:
            raise RuntimeError('Camera disconnected during duplicate check.')
        frames += 1
        gray, boxes = crop_faces(frame, cascade)
        if len(boxes) == 1:
            x, y, w, h = boxes[0]
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 210, 255), 2)
            if frames % 3 == 0:
                candidates.append(cv2.resize(gray[y:y+h, x:x+w], (200, 200)))
        cv2.putText(frame, f'Checking prior enrollment {len(candidates)}/24 - Q cancels',
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 210, 255), 2)
        cv2.imshow('Register Student', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            raise RuntimeError('Registration cancelled.')
    if len(candidates) != 24:
        raise RuntimeError('Unable to complete face check; no new student added.')
    match = duplicate_evidence(candidates, people, images, labels)
    if match:
        sid, name, count = match
        raise DuplicateFaceError(
            f'Possible existing student: {name} (ID {sid}), '
            f'{count}/24 matching frames. Verify in the student list.'
        )
    print('No strong duplicate indication found; proceed with enrollment. '
          'This is not proof of a unique identity.')


def check_captured_face(folder):
    """Second gate after capture: no DB insert until face samples pass."""
    people, images, labels = existing_face_samples()
    if not people:
        return
    candidates = []
    for path in sorted(folder.glob('*.png')):
        face = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if face is not None:
            candidates.append(cv2.resize(face, (200, 200)))
    if len(candidates) < 10:
        raise RuntimeError('Insufficient captured face samples.')
    match = duplicate_evidence(candidates, people, images, labels)
    if match:
        sid, name, count = match
        raise DuplicateFaceError(
            f'Possible existing student: {name} (ID {sid}), '
            f'{count}/{len(candidates)} captured samples matched. Manual review required.')

def register(student_id, name):
    con = connect()
    if con.execute('SELECT 1 FROM students WHERE id=?', (student_id,)).fetchone():
        con.close()
        raise ValueError('Student ID already exists; choose a new ID')
    normalized = ' '.join(name.split()).casefold()
    for existing_id, existing_name in con.execute('SELECT id, name FROM students'):
        if ' '.join(existing_name.split()).casefold() == normalized:
            con.close()
            raise ValueError(f'Student already registered as ID {existing_id}: {existing_name}')
    con.close()
    cascade = detector()
    cam = camera()
    folder = FACES / str(student_id)
    saved = 0
    frame_num = 0
    print('Look at camera and slowly change head angle. Press Q to stop.')
    try:
        check_existing_face(cam, cascade)
        if folder.exists() and any(folder.iterdir()):
            raise RuntimeError('Face samples already exist for this ID; contact admin.')
        folder.mkdir(exist_ok=True)
        while saved < 35:
            ok, frame = cam.read()
            if not ok:
                break
            gray, boxes = crop_faces(frame, cascade)
            if len(boxes) == 1:
                x, y, w, h = boxes[0]
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                frame_num += 1
                if frame_num % 4 == 0:
                    face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
                    cv2.imwrite(str(folder / f'{saved:03d}.png'), face)
                    saved += 1
            cv2.putText(frame, f'Saved {saved}/35 (Q to quit)', (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2)
            cv2.imshow('Register Student', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
    if saved < 10:
        if folder.exists():
            for file in folder.glob('*.png'):
                file.unlink()
            folder.rmdir()
        raise RuntimeError('Not enough samples captured; try again')
    try:
        check_captured_face(folder)
    except Exception:
        for path in folder.glob('*.png'):
            path.unlink()
        if folder.exists():
            folder.rmdir()
        raise
    con = connect()
    con.execute('INSERT INTO students(id, name) VALUES(?, ?)', (student_id, name))
    con.commit()
    con.close()
    print(f'Registered {name}: {saved} face samples. Run train next.')


def train():
    connect().close()
    imgs, ids = [], []
    for folder in FACES.iterdir():
        if not folder.is_dir() or not folder.name.isdigit():
            continue
        for file in folder.glob('*.png'):
            img = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                imgs.append(cv2.resize(img, (200, 200)))
                ids.append(int(folder.name))
    if not imgs:
        raise RuntimeError('No face samples yet. Register a student first.')
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(imgs, np.array(ids, dtype=np.int32))
    recognizer.write(str(MODEL))
    print(f'Trained with {len(imgs)} images from {len(set(ids))} students.')


def attendance():
    if not MODEL.exists():
        raise RuntimeError('Model missing. Run train first.')
    con = connect()
    names = dict(con.execute('SELECT id, name FROM students').fetchall())
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(MODEL))
    cascade = detector()
    cam = camera()
    # LBPH distance threshold is heuristic and must be tested locally.
    threshold = 55
    streaks = {}
    print('Press Q to quit. Present only consented, registered students.')
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                break
            gray, boxes = crop_faces(frame, cascade)
            seen = set()
            for x, y, w, h in boxes:
                face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
                sid, distance = recognizer.predict(face)
                identified = sid in names and distance < threshold
                label = f'{names[sid]} ({distance:.0f})' if identified else 'Unknown'
                color = (0, 200, 0) if identified else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, label, (x, max(y-10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, .65, color, 2)
                if identified:
                    seen.add(sid)
                    streaks[sid] = streaks.get(sid, 0) + 1
                    if streaks[sid] == 8:
                        now = datetime.now()
                        cur = con.execute('INSERT OR IGNORE INTO attendance(student_id,date,time) VALUES(?,?,?)',
                                          (sid, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')))
                        con.commit()
                        if cur.rowcount:
                            print(f'Attendance marked: {names[sid]} at {now:%H:%M:%S}')
            for sid in list(streaks):
                if sid not in seen:
                    streaks[sid] = 0
            cv2.imshow('Face Attendance (Q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
        con.close()


def report():
    con = connect()
    rows = con.execute('''SELECT a.date, a.time, a.student_id, s.name FROM attendance a
                          JOIN students s ON s.id = a.student_id ORDER BY a.date DESC, a.time DESC''').fetchall()
    con.close()
    path = ROOT / 'attendance_report.csv'
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Time', 'Student ID', 'Name'])
        writer.writerows(rows)
    print(f'Exported {len(rows)} records to {path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Local face attendance learning project')
    sub = parser.add_subparsers(dest='command', required=True)
    reg = sub.add_parser('register')
    reg.add_argument('--id', type=int, required=True)
    reg.add_argument('--name', required=True)
    sub.add_parser('train')
    sub.add_parser('attendance')
    sub.add_parser('report')
    args = parser.parse_args()
    try:
        if args.command == 'register':
            register(args.id, args.name)
        elif args.command == 'train':
            train()
        elif args.command == 'attendance':
            attendance()
        else:
            report()
    except DuplicateFaceError as e:
        print(f'ALREADY REGISTERED: {e}', flush=True)
        sys.exit(3)
    except (RuntimeError, ValueError, cv2.error) as e:
        print(f'Error: {e}', flush=True)
        sys.exit(1)
