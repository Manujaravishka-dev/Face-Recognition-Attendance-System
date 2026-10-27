import argparse
import csv
import sqlite3
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


def register(student_id, name):
    con = connect()
    if con.execute('SELECT 1 FROM students WHERE id=?', (student_id,)).fetchone():
        con.close()
        raise ValueError('Student ID already exists; choose a new ID')
    con.close()
    folder = FACES / str(student_id)
    folder.mkdir(exist_ok=True)
    cascade = detector()
    cam = camera()
    saved = 0
    frame_num = 0
    print('Look at camera and slowly change head angle. Press Q to stop.')
    try:
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
        for file in folder.glob('*.png'):
            file.unlink()
        folder.rmdir()
        raise RuntimeError('Not enough samples captured; try again')
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
    except (RuntimeError, ValueError, cv2.error) as e:
        print(f'Error: {e}')
