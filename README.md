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

### Face-based duplicate detection before registration

When a trained `model.yml` exists, **Capture & Auto Train** first shows a webcam verification stage (`Face check 0/24`). It compares the presented face with registered students for repeated, strong LBPH matches. If one is found, registration is blocked and the dashboard displays **Already Registered**; the camera briefly shows a possible matching name and ID. Otherwise the usual photo collection begins and the model trains automatically after successful enrollment.

This is a *possible-match warning*, **not reliable proof of identity**. Similar-looking people may be falsely blocked and the same person might go undetected. Staff must verify matches manually. If an existing student was accidentally registered twice before this update, remove the mistaken record and retrain before using the check. A missing trained model means there is no face-based duplicate check for the first registration.

## Enhanced desktop dashboard (2026)

Run:
```powershell
py -m pip install -r requirements.txt
py dashboard.py
```

The updated Python Tkinter dashboard includes:
- **Embedded live camera** after clicking Start Camera; Stop Camera releases the webcam
- **Automatic attendance** for repeatedly detected, previously registered faces
- **Unknown-face label** (not automatic registration)
- **Edit Profile** for correcting a selected student's name
- **Analytics** chart for up to 12 recent recorded days
- Student search, CSV export, consent-based face registration, training, duplicate checks, data backup and deletion

Stop the live preview before running face enrollment; the same webcam cannot safely be opened twice. Embedded attendance uses the existing LBPH model, so scores are estimates, not verified identities. A human should review false matches and correct attendance where necessary.

The camera and interface need testing on your own Windows machine. No web dashboard, admin password protection, liveness detection, or packaged EXE is included in this stage; these require further development. Do not expose the local database, photos, or unencrypted backup ZIP publicly.

## Student Profile Management

Select a student in the dashboard's **Students** table and click **Edit Profile**. The profile window shows an existing local face sample (if one was captured), the student's ID, editable full name, class/group, optional phone and up to 300 recent attendance entries. Click **Save Profile** to update SQLite. Existing students are supported without migration commands; profile details are stored in a separate `student_profiles` table created automatically on first use. For legacy student records, the original registration date was not recorded and is shown as unavailable until a profile is saved (the saved profile's creation date is recorded).

Deleting a student from the dashboard also deletes that student's supplementary profile. No phone or face image is pushed to GitHub. Treat these details and ZIP backups as private.

## Registration security: double duplicate screening

New enrollment now compares webcam samples against *actual saved face samples for every enrolled student*, independent of whether the current `model.yml` is up to date. A second check runs after capturing 35 images and **before** inserting any new student record. When a potential match is detected, registration is blocked and the captured provisional images are discarded. If prior enrolled photos are missing or insufficient, enrollment fails closed instead of silently skipping duplicate checks.

**This is a conservative heuristic, not identity proof.** False negatives and false positives are still possible; especially for similar-looking people, poor lighting, face angles, or images recorded under different conditions. An operator must cross-check school ID or another reliable unique enrollment credential and perform a manual review of possible duplicates. Do not use this to enforce disciplinary consequences or automatically delete existing students. Existing duplicates are **not** silently merged or deleted; they require deliberate administrator review.

To test: back up local attendance data, close the camera, pull the latest changes, launch the dashboard and attempt a registration with consent. An **Already Registered** warning indicates a *possible* match, not a conclusive identification.
