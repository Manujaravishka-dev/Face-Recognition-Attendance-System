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

## Phase 3: Optional Deep Learning Face Duplicate Check

Official OpenCV Zoo models: YuNet detector and SFace embedding recognizer.

```powershell
git pull origin main
py -m pip install -r requirements.txt
py setup_deep_models.py
py dashboard.py
```

The setup script downloads the models once into the ignored local `models/` directory. Do not commit model binaries or student biometrics. To enable the optional deep-learning check, **both models must download successfully**. If they are absent, the existing LBPH duplicate screening remains enabled. When installed, SFace checks newly captured face samples against previously captured samples **before** the student record is saved. A possible duplicate halts enrollment for human review. If the model cannot inspect enough faces, registration pauses for review rather than claiming a safe match.

**Important limitations:** Existing images are small grayscale LBPH crops, not full-color five-landmark images; SFace may be unable to extract embeddings for them. That deliberately blocks enrollment when the deep gallery is incomplete. For reliable future results, we should add consented full-frame multi-angle enrollment photos and calibrate face-matching thresholds against test data. This phase does **not** replace attendance recognition with SFace and does not guarantee that differently named registrations will always be detected. Always confirm a school ID or other authoritative identifier.

Face matching accuracy and ONNX model compatibility must be tested on the target Windows/OpenCV installation; this change has not been camera-tested remotely.

## Phase 4: Multi-angle enrollment + SFace live preview (experimental)

New webcam registration retains existing 200x200 LBPH crops **and** saves locally held full-color camera frames in ignored `faces_full/<student_id>/`. During enrollment look front, then slightly left and right, ensuring just one face stays in view. Existing students' original images cannot be reconstructed; they must be voluntarily re-enrolled to obtain full-frame samples.

When both optional OpenCV Zoo models are installed AND the SFace face gallery can be built for **all** registered students, the embedded Dashboard camera shows `LIVE (SFace)`. Otherwise it falls back to `LIVE (LBPH)`. Deep recognition currently accepts one visible face per frame and requires 8 successive matches before marking attendance. The existing CLI attendance still uses LBPH. The original 35 samples are saved locally, not uploaded.

**Experimental:** The heuristic SFace similarity and ambiguity thresholds have not been calibrated for your camera or for different people. It can still give false positives/negatives; do not use automatic matches as an unquestionable source of attendance truth. Keep manual corrections available. Full-color student photos are highly sensitive biometric data: obtain consent, restrict access to the PC and backups, and never push `faces_full` or `attendance.db` to public GitHub.

Setup: `git pull origin main`, `py -m pip install -r requirements.txt`, optionally `py setup_deep_models.py`, then `py dashboard.py`. For first use, make a private backup and validate using consented test students. Existing enrolled faces require re-enrollment before expecting reliable SFace recognition.
