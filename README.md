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

## Desktop Admin Dashboard

Run after installing dependencies:

```powershell
py dashboard.py
```

Dashboard features:
- Live counts: registered, present today, not marked today and total attendance records
- Student list with daily attendance status
- Attendance history table
- Register a student via webcam (consent confirmation)
- Train face recognition model
- Start and stop recognition camera
- Export displayed attendance history as CSV

**Important:** The camera opens in a separate OpenCV window, not embedded in the dashboard. You can close the camera with **Q**. After registering new faces, click **Train Model** before using attendance again. You can also run the existing CLI commands as before.

On some Linux installations Tkinter needs the separate `python3-tk` OS package. Tkinter is included in most official Windows Python installations.

The face-recognition implementation is a local education demo, not a high-assurance identity system. Obtain informed consent; do not publish any faces, databases or trained model files. Verify attendance manually where needed.

### One-click registration and automatic training

In the desktop dashboard, enter a **new numeric student ID** and **student name**, then click **Capture & Auto Train**. Confirm the student's consent. The webcam captures 35 samples (at least 10 are required); after the camera closes successfully, the dashboard **automatically retrains the recognition model using all registered students**. Manual Train Model remains available. Do not close the dashboard while training. Previously registered students and attendance records remain local and are not deleted.

### Duplicate student prevention

New registration rejects an existing student ID or an existing student name after trimming spaces and ignoring letter case. Select a duplicate in the Students table and use **Delete Selected Student** to remove that selected ID, its attendance history and local face samples after confirmation; the remaining face model is retrained. Back up local data first if you need to preserve it.

**Limit:** Name matching does not prove two people have the same identity. A person registered under a different name and ID is not automatically identified as a duplicate. Distinct people sharing a name will also be blocked until the registration policy is improved (e.g., an additional unique school ID).
