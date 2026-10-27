"""Desktop dashboard for the Face Recognition Attendance System.

Uses Python's built-in Tkinter; webcam sessions run in separate processes.
"""
import csv
import cv2
import numpy as np
from PIL import Image, ImageTk
from datetime import datetime
import tempfile
import zipfile
import shutil
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
DB = ROOT / "attendance.db"
MAIN = ROOT / "main.py"

BG = "#0b1220"
PANEL = "#172338"
CARD = "#1d2e46"
FG = "#f1f5fa"
MUTED = "#a6bad1"
ACCENT = "#40bfae"


def read_data():
    with sqlite3.connect(DB) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("""CREATE TABLE IF NOT EXISTS attendance (
            student_id INTEGER NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
            PRIMARY KEY(student_id, date))""")
        students = connection.execute("SELECT id, name FROM students ORDER BY id").fetchall()
        records = connection.execute("""SELECT a.date, a.time, a.student_id, COALESCE(s.name, 'Unknown')
            FROM attendance a LEFT JOIN students s ON s.id=a.student_id
            ORDER BY a.date DESC, a.time DESC LIMIT 1000""").fetchall()
    return students, records


class Dashboard:
    def __init__(self, root):
        self.root = root
        root.title("Face Recognition | Attendance Dashboard")
        root.geometry("1200x900")
        root.minsize(850, 580)
        root.configure(bg=BG)
        self.process = None
        self.auto_train = False
        self.training = False
        self.registration_id = None
        self.live_capture = None
        self.deep_verifier = None
        self.live_mode = 'LBPH'
        self.live_model = None
        self.live_detector = None
        self.live_names = {}
        self.live_hits = {}
        self.live_photo = None

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=FG, fieldbackground=PANEL,
                        rowheight=31, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=CARD, foreground=FG,
                        font=("Segoe UI", 10, "bold"), padding=9)
        style.map("Treeview", background=[("selected", "#256f79")])
        style.configure("TCombobox", padding=5)

        outer = tk.Frame(root, bg=BG, padx=26, pady=20)
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text="ATTENDANCE CONTROL CENTER", font=("Segoe UI", 11, "bold"),
                 bg=BG, fg=ACCENT).pack(anchor="w")
        tk.Label(outer, text="Face Recognition Dashboard", font=("Segoe UI", 25, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", pady=(2, 4))
        tk.Label(outer, text="Local student management, live recognition and attendance records",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 18))

        metrics = tk.Frame(outer, bg=BG)
        metrics.pack(fill="x", pady=(0, 18))
        self.metric_labels = {}
        for i, (key, title) in enumerate([("total", "REGISTERED STUDENTS"),
                                           ("present", "PRESENT TODAY"),
                                           ("absent", "NOT MARKED TODAY"),
                                           ("records", "TOTAL RECORDS")]):
            cell = tk.Frame(metrics, bg=CARD, padx=18, pady=16)
            cell.grid(row=0, column=i, padx=(0 if i == 0 else 6, 6 if i != 3 else 0),
                      sticky="ew")
            metrics.grid_columnconfigure(i, weight=1, uniform="metric")
            tk.Label(cell, text=title, fg=MUTED, bg=CARD,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            label = tk.Label(cell, text="0", fg=FG, bg=CARD,
                             font=("Segoe UI", 27, "bold"))
            label.pack(anchor="w", pady=(5, 0))
            self.metric_labels[key] = label

        actions = tk.Frame(outer, bg=PANEL, padx=14, pady=12)
        actions.pack(fill="x", pady=(0, 17))
        self.button(actions, "Start Camera", self.start_camera).pack(side="left", padx=(0, 8))
        self.button(actions, "Stop Camera", self.stop_camera, dark=True).pack(side="left", padx=(0, 8))
        self.button(actions, "Train Model", self.train_model, dark=True).pack(side="left", padx=(0, 8))
        self.button(actions, "Export CSV", self.export_csv, dark=True).pack(side="left", padx=(0, 8))
        self.button(actions, "Refresh", self.refresh, dark=True).pack(side="left", padx=(0, 8))
        self.button(actions, "Backup Data", self.backup_data, dark=True).pack(side="left", padx=(0, 8))
        self.button(actions, "Analytics", self.show_analytics, dark=True).pack(side="left")

        entryrow = tk.Frame(outer, bg=PANEL, padx=14, pady=14)
        entryrow.pack(fill="x", pady=(0, 18))
        tk.Label(entryrow, text="Register Student", font=("Segoe UI", 12, "bold"),
                 bg=PANEL, fg=FG).pack(side="left", padx=(0, 14))
        self.id_entry = tk.Entry(entryrow, width=9, font=("Segoe UI", 11))
        self.id_entry.pack(side="left", padx=(0, 10), ipady=6)
        self.id_entry.insert(0, "ID")
        self.name_entry = tk.Entry(entryrow, width=24, font=("Segoe UI", 11))
        self.name_entry.pack(side="left", padx=(0, 10), ipady=6)
        self.name_entry.insert(0, "Student Name")
        self.button(entryrow, "Capture & Auto Train", self.register_student).pack(side="left")

        livebox = tk.Frame(outer, bg=PANEL, padx=12, pady=10)
        livebox.pack(fill="x", pady=(0, 15))
        self.live_image_label = tk.Label(livebox, text="Camera offline - click Start Camera",
                                          width=65, height=12, bg="#101b2c", fg=FG)
        self.live_image_label.pack(side="left")
        details = tk.Frame(livebox, bg=PANEL, padx=20)
        details.pack(side="left", fill="both", expand=True)
        tk.Label(details, text="LIVE FACE RECOGNITION", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 6))
        self.live_status = tk.StringVar(value="OFFLINE")
        tk.Label(details, textvariable=self.live_status, bg=PANEL, fg=FG,
                 font=("Segoe UI", 12)).pack(anchor="w")
        tk.Label(details, text="Registered matches are marked once per day.\n"
                 "Unknown faces are never enrolled automatically.",
                 bg=PANEL, fg=MUTED, justify="left").pack(anchor="w", pady=(14, 0))

        tables = tk.Frame(outer, bg=BG)
        tables.pack(fill="both", expand=True)
        tables.grid_columnconfigure(0, weight=2)
        tables.grid_columnconfigure(1, weight=3)
        tables.grid_rowconfigure(0, weight=1)

        left = tk.Frame(tables, bg=PANEL, padx=13, pady=12)
        right = tk.Frame(tables, bg=PANEL, padx=13, pady=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        student_header = tk.Frame(left, bg=PANEL)
        student_header.pack(fill="x", pady=(0, 12))
        tk.Label(student_header, text="Students", bg=PANEL, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Button(student_header, text="Edit Profile", command=self.edit_student,
                  bg=CARD, fg=FG, font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", padx=10, pady=6).pack(side="right", padx=(0, 8))
        tk.Button(student_header, text="Delete Student", command=self.delete_student,
                  bg="#a93646", fg="#ffffff", activebackground="#c34a59",
                  activeforeground="#ffffff", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", padx=10, pady=6).pack(side="right")
        search_bar = tk.Frame(left, bg=PANEL)
        search_bar.pack(fill="x", pady=(0, 10))
        tk.Label(search_bar, text="Search:", bg=PANEL, fg=MUTED).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.filter_students())
        tk.Entry(search_bar, textvariable=self.search_var,
                 font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.cached_students = []
        tk.Label(right, text="Attendance History", bg=PANEL, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 12))

        self.students = ttk.Treeview(left, columns=("id", "name", "status"),
                                     show="headings", selectmode="browse")
        for col, label, width in [("id", "ID", 60), ("name", "Student", 160),
                                  ("status", "Today", 90)]:
            self.students.heading(col, text=label)
            self.students.column(col, width=width, minwidth=55, stretch=True)
        self.students.pack(fill="both", expand=True)

        self.history = ttk.Treeview(right, columns=("date", "time", "id", "name"),
                                    show="headings")
        for col, label, width in [("date", "Date", 115), ("time", "Time", 80),
                                  ("id", "ID", 55), ("name", "Student", 155)]:
            self.history.heading(col, text=label)
            self.history.column(col, width=width, minwidth=45, stretch=True)
        self.history.pack(fill="both", expand=True)

        self.status = tk.StringVar(value="Ready")
        tk.Label(outer, textvariable=self.status, fg=MUTED, bg=BG,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(11, 0))
        self.refresh()
        root.after(3500, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def button(self, parent, title, command, dark=False):
        return tk.Button(parent, text=title, command=command,
                         font=("Segoe UI", 10, "bold"), bg=CARD if dark else ACCENT,
                         fg=FG if dark else BG, activebackground="#2a8b8d",
                         relief="flat", cursor="hand2", padx=13, pady=8)

    def refresh(self):
        try:
            students, records = read_data()
        except (sqlite3.Error, OSError) as exc:
            messagebox.showerror("Database error", str(exc))
            return
        today = date.today().isoformat()
        marked = {row[2] for row in records if row[0] == today}
        values = {"total": len(students), "present": len(marked),
                  "absent": sum(sid not in marked for sid, _ in students),
                  "records": self.count_records()}
        for key, value in values.items():
            self.metric_labels[key].configure(text=str(value))
        for tree in (self.students, self.history):
            tree.delete(*tree.get_children())
        self.cached_students = [(sid, name, "Present" if sid in marked else "Pending")
                                for sid, name in students]
        self.filter_students()
        for row in records:
            self.history.insert("", "end", values=row)
        self.status.set("Data refreshed. Attendance is counted once per student per day.")

    def filter_students(self):
        term = self.search_var.get().strip().casefold()
        self.students.delete(*self.students.get_children())
        for row in self.cached_students:
            if term in str(row[0]).casefold() or term in row[1].casefold():
                self.students.insert("", "end", values=row)

    def backup_data(self):
        if self.training or (self.process and self.process.poll() is None):
            messagebox.showwarning("Busy", "Stop camera sessions and finish training before backup.")
            return
        target = filedialog.asksaveasfilename(
            title="Save private student backup",
            defaultextension=".zip",
            initialfile=f"face_attendance_backup_{date.today().isoformat()}.zip",
            filetypes=[("ZIP archive", "*.zip")])
        if not target:
            return
        try:
            with tempfile.TemporaryDirectory() as temporary:
                snapshot = Path(temporary) / "attendance.db"
                with sqlite3.connect(DB) as source, sqlite3.connect(snapshot) as destination:
                    source.backup(destination)
                with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.write(snapshot, "attendance.db")
                    for dirname in ("faces", "faces_full"):
                        folder = ROOT / dirname
                        if folder.is_dir():
                            for path in folder.rglob("*"):
                                if path.is_file():
                                    archive.write(path, path.relative_to(ROOT))
                    model = ROOT / "model.yml"
                    if model.is_file():
                        archive.write(model, "model.yml")
            messagebox.showinfo("Backup created",
                                "Private backup saved. Keep it secure; it contains biometric face data.")
            self.status.set("Backup created successfully.")
        except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
            messagebox.showerror("Backup failed", str(exc))

    def count_records(self):
        with sqlite3.connect(DB) as connection:
            return connection.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]

    def launch(self, args, label, auto_train=False):
        if self.live_capture is not None:
            messagebox.showwarning("Camera busy", "Stop live preview before registration.")
            return
        if self.training:
            messagebox.showinfo("Training in progress", "Finish model training before using the camera.")
            return
        if self.process is not None and self.process.poll() is None:
            messagebox.showinfo("Camera in use", "Close the current camera window with Q first.")
            return
        try:
            self.process = subprocess.Popen([sys.executable, str(MAIN), *args], cwd=ROOT)
            self.auto_train = auto_train
            self.registration_id = int(args[args.index("--id") + 1]) if auto_train else None
            self.status.set(label + " — press Q in the camera window to finish")
        except OSError as exc:
            messagebox.showerror("Unable to start", str(exc))

    def start_camera(self):
        if self.training or (self.process and self.process.poll() is None):
            messagebox.showwarning("Busy", "Finish face registration or training first.")
            return
        if self.live_capture is not None:
            return
        try:
            from main import detector
            model_path = ROOT / "model.yml"
            if not model_path.exists():
                messagebox.showwarning("Model missing", "Register and train a face first.")
                return
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.read(str(model_path))
            cascade = detector()
            capture = cv2.VideoCapture(0)
            if not capture.isOpened():
                capture.release()
                raise RuntimeError("Could not open webcam.")
            with sqlite3.connect(DB) as con:
                names = dict(con.execute("SELECT id,name FROM students"))
            self.deep_verifier = None
            self.live_mode = "LBPH"
            try:
                from deep_face import DeepFaceVerifier, installed
                if installed() and names:
                    verifier = DeepFaceVerifier()
                    gallery = verifier.build_gallery(ROOT / "faces", names)
                    # Never recognize with an incomplete gallery.
                    if set(gallery) == set(names):
                        self.deep_verifier = verifier
                        self.live_mode = "SFace"
            except (RuntimeError, cv2.error, OSError):
                pass
            self.live_model = recognizer
            self.live_detector = cascade
            self.live_names = names
            self.live_hits = {}
            self.live_capture = capture
            self.live_status.set("LIVE - camera active")
            self.root.after(30, self.camera_frame)
        except Exception as exc:
            self.stop_camera()
            messagebox.showerror("Camera error", str(exc))

    def camera_frame(self):
        if self.live_capture is None:
            return
        try:
            ok, frame = self.live_capture.read()
            if not ok:
                raise RuntimeError("Camera stopped sending frames.")
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            boxes = self.live_detector.detectMultiScale(
                gray, scaleFactor=1.2, minNeighbors=5, minSize=(90, 90))
            seen = set()
            for x, y, w, h in boxes:
                face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
                if self.deep_verifier is not None:
                    result = self.deep_verifier.predict(frame[y:y+h, x:x+w])
                    sid = result[0] if result else -1
                    recognized = sid in self.live_names
                else:
                    sid, distance = self.live_model.predict(face)
                    recognized = sid in self.live_names and distance < 55
                label = self.live_names[sid] if recognized else "Unknown"
                color = (40, 205, 125) if recognized else (50, 80, 235)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, label[:26], (x, max(y-8, 25)),
                            cv2.FONT_HERSHEY_SIMPLEX, .65, color, 2)
                if recognized:
                    seen.add(sid)
                    self.live_hits[sid] = self.live_hits.get(sid, 0) + 1
                    if self.live_hits[sid] == 8:
                        now = datetime.now()
                        with sqlite3.connect(DB) as con:
                            con.execute("INSERT OR IGNORE INTO attendance(student_id,date,time) VALUES(?,?,?)",
                                        (sid, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")))
                        self.refresh()
            for sid in list(self.live_hits):
                if sid not in seen:
                    self.live_hits[sid] = 0
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb = cv2.resize(rgb, (440, 260))
            photo = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.live_photo = photo
            self.live_image_label.configure(image=photo, text="", width=440, height=260)
            self.live_status.set(f"LIVE ({self.live_mode}) - {len(boxes)} face(s) detected")
        except Exception as exc:
            self.stop_camera()
            self.live_status.set("Camera error")
            messagebox.showerror("Camera error", str(exc))
            return
        self.root.after(35, self.camera_frame)

    def stop_camera(self):
        if self.live_capture is not None:
            self.live_capture.release()
            self.live_capture = None
        self.live_photo = None
        self.live_image_label.configure(image="", text="Camera offline - click Start Camera")
        self.live_status.set("OFFLINE")
        if self.process and self.process.poll() is None:
            if messagebox.askyesno("Stop capture", "Stop the current registration session?"):
                self.process.terminate()
        self.root.after(200, self.refresh)

    def register_student(self):
        sid = self.id_entry.get().strip()
        name = self.name_entry.get().strip()
        if not sid.isdigit() or int(sid) < 1 or not name or name == "Student Name":
            messagebox.showwarning("Invalid data", "Enter a positive numeric ID and student name.")
            return
        if len(name) > 100:
            messagebox.showwarning("Invalid data", "Name must be 100 characters or fewer.")
            return
        students, _ = read_data()
        for existing_id, existing_name in students:
            if int(sid) == existing_id:
                messagebox.showwarning("Duplicate ID", f"Student ID {sid} is already registered.")
                return
            if " ".join(existing_name.split()).casefold() == " ".join(name.split()).casefold():
                messagebox.showwarning("Duplicate student",
                    f"{existing_name} is already registered with ID {existing_id}.\n"
                    "Use the existing record instead of registering twice.")
                return
        if not messagebox.askyesno("Consent", "Confirm this student has consented to local face-image capture."):
            return
        self.launch(["register", "--id", sid, "--name", name], f"Capturing face for {name}", auto_train=True)

    def edit_student(self):
        if self.training or self.live_capture is not None or (self.process and self.process.poll() is None):
            messagebox.showwarning("Busy", "Stop the camera before opening a profile.")
            return
        selected = self.students.selection()
        if not selected:
            messagebox.showinfo("Select Student", "Select a student from the table first.")
            return
        sid = int(self.students.item(selected[0], "values")[0])
        from student_profile import open_profile
        open_profile(self.root, sid, self.refresh)

    def show_analytics(self):
        with sqlite3.connect(DB) as con:
            total = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            rows = con.execute("SELECT date,COUNT(*) FROM attendance GROUP BY date ORDER BY date DESC LIMIT 30").fetchall()
        window = tk.Toplevel(self.root)
        window.title("Attendance Analytics")
        window.geometry("550x490")
        window.configure(bg=BG)
        tk.Label(window, text="Attendance Analytics - Last 30 recorded days",
                 bg=BG, fg=FG, font=("Segoe UI", 14, "bold")).pack(pady=17)
        canvas = tk.Canvas(window, bg=PANEL, height=360, highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=18, pady=12)
        if not rows:
            canvas.create_text(230, 150, text="No attendance records yet", fill=FG)
            return
        for i, (day, count) in enumerate(rows[:12]):
            y = 20+i*27
            canvas.create_text(85, y+10, text=day, fill=FG)
            canvas.create_rectangle(135, y, 135+int(260*count/max(total,1)), y+18,
                                    fill=ACCENT, outline="")
            canvas.create_text(420, y+10, text=f"{count}/{total}", fill=FG)

    def delete_student(self):
        if self.training or (self.process and self.process.poll() is None):
            messagebox.showwarning("Busy", "Close the camera and finish training first.")
            return
        selected = self.students.selection()
        if not selected:
            messagebox.showinfo("Select student", "Select the duplicate row to remove.")
            return
        sid, name, _ = self.students.item(selected[0], "values")
        if not messagebox.askyesno(
            "Delete student",
            f"Permanently remove {name} (ID {sid})?\n\n"
            "Their face samples and attendance records will also be deleted. "
            "This cannot be undone.",
        ):
            return
        try:
            with sqlite3.connect(DB) as connection:
                connection.execute("DELETE FROM attendance WHERE student_id=?", (int(sid),))
                connection.execute("DELETE FROM students WHERE id=?", (int(sid),))
                connection.execute("""CREATE TABLE IF NOT EXISTS student_profiles (
                    student_id INTEGER PRIMARY KEY, class_name TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    registered_on TEXT NOT NULL DEFAULT (date('now')))""")
                connection.execute("DELETE FROM student_profiles WHERE student_id=?", (int(sid),))
            shutil.rmtree(ROOT / "faces" / str(int(sid)), ignore_errors=True)
            shutil.rmtree(ROOT / "faces_full" / str(int(sid)), ignore_errors=True)
            self.refresh()
            with sqlite3.connect(DB) as connection:
                count = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            if count:
                self.train_model()
            else:
                (ROOT / "model.yml").unlink(missing_ok=True)
                self.status.set("All students removed. Model cleared.")
        except (sqlite3.Error, OSError) as exc:
            messagebox.showerror("Delete failed", str(exc))

    def train_model(self):
        if self.training:
            return
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Camera active", "Finish the camera session first.")
            return
        self.training = True
        self.status.set("Training model...")
        def worker():
            result = subprocess.run([sys.executable, str(MAIN), "train"], cwd=ROOT,
                                    text=True, capture_output=True)
            def done():
                self.training = False
                self.status.set("Model trained" if result.returncode == 0 else "Training failed")
                self.refresh()
                messagebox.showinfo("Training result", (result.stdout + "\n" + result.stderr).strip())
            self.root.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def export_csv(self):
        try:
            _, records = read_data()
            filename = filedialog.asksaveasfilename(defaultextension=".csv",
                         initialfile=f"attendance_{date.today().isoformat()}.csv",
                         filetypes=[("CSV files", "*.csv")])
            if not filename:
                return
            with open(filename, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["Date", "Time", "Student ID", "Name"])
                writer.writerows(records)
            self.status.set(f"Exported {len(records)} visible records to {filename}")
        except (OSError, sqlite3.Error) as exc:
            messagebox.showerror("Export failed", str(exc))

    def poll(self):
        if self.process and self.process.poll() is not None:
            exit_code = self.process.returncode
            was_registration = self.auto_train
            student_id = self.registration_id
            self.process = None
            self.auto_train = False
            self.registration_id = None
            self.refresh()
            if was_registration:
                with sqlite3.connect(DB) as connection:
                    registered = connection.execute(
                        "SELECT 1 FROM students WHERE id=?", (student_id,)
                    ).fetchone() is not None
                if exit_code == 0 and registered:
                    self.status.set("Face captured successfully. Auto training model...")
                    self.train_model()
                elif exit_code == 3:
                    self.status.set("Already Registered - possible face match. Enrollment blocked.")
                    messagebox.showwarning(
                        "Already Registered",
                        "This face appears to match an existing registered student.\n\n"
                        "No new student was added. Please verify the match with the "
                        "student list before trying again."
                    )
                else:
                    self.status.set("Registration incomplete. Model was not trained.")
                    messagebox.showwarning(
                        "Registration incomplete",
                        "Enrollment was cancelled or failed. Check the camera window "
                        "and terminal for details. No new student was added."
                    )
        else:
            self.refresh_silent()
        self.root.after(3500, self.poll)

    def refresh_silent(self):
        # Update records while camera runs; avoids clearing UI while scrolling constantly.
        if not self.process:
            return
        try:
            total = self.count_records()
            if int(self.metric_labels["records"].cget("text")) != total:
                self.refresh()
        except (ValueError, sqlite3.Error, OSError):
            pass

    def close(self):
        if self.live_capture is not None:
            self.stop_camera()
        if self.training:
            messagebox.showinfo("Please finish training", "Close after model training is complete.")
            return
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Camera still running", "Stop camera and exit dashboard?"):
                return
            self.process.terminate()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    Dashboard(window)
    window.mainloop()
