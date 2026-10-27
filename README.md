# Face Recognition Attendance System

A Python webcam-based student attendance learning project using OpenCV LBPH and SQLite.

## Features
- Register students and capture face images locally
- Train a face recognition model
- Mark attendance once per student per day
- Export an attendance CSV report

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Commands

```powershell
.\.venv\Scripts\python.exe main.py register --id 1 --name "Student Name"
.\.venv\Scripts\python.exe main.py train
.\.venv\Scripts\python.exe main.py attendance
.\.venv\Scripts\python.exe main.py report
```

Use a webcam and grant camera permission. Press Q to exit camera windows.

## Privacy and reliability
Educational prototype only. Obtain consent for face-image collection. Review and correct attendance manually; recognition can make mistakes. Face samples, trained models, and SQLite data are kept local and excluded by .gitignore.
