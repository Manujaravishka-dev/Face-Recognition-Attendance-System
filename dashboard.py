"""Desktop dashboard for the Face Recognition Attendance System.

Uses Python's built-in Tkinter; webcam sessions run in separate processes.
"""
import csv
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
        root.geometry("1120x740")
        root.minsize(850, 580)
        root.configure(bg=BG)
        self.process = None
        self.auto_train = False
        self.training = False
        self.registration_id = None

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
        self.button(actions, "Refresh", self.refresh, dark=True).pack(side="left")

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

        tables = tk.Frame(outer, bg=BG)
        tables.pack(fill="both", expand=True)
        tables.grid_columnconfigure(0, weight=2)
        tables.grid_columnconfigure(1, weight=3)
        tables.grid_rowconfigure(0, weight=1)

        left = tk.Frame(tables, bg=PANEL, padx=13, pady=12)
        right = tk.Frame(tables, bg=PANEL, padx=13, pady=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        tk.Label(left, text="Students", bg=PANEL, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 12))
        tk.Label(right, text="Attendance History", bg=PANEL, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 12))

        self.students = ttk.Treeview(left, columns=("id", "name", "status"),
                                     show="headings", selectmode="browse")
        for col, label, width in [("id", "ID", 60), ("name", "Student", 160),
                                  ("status", "Today", 90)]:
            self.students.heading(col, text=label)
            self.students.column(col, width=width, minwidth=55, stretch=True)
        self.students.pack(fill="both", expand=True)
        self.button(left, "Delete Selected Student", self.delete_student, dark=True).pack(
            anchor="w", pady=(10, 0))

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
        for sid, name in students:
            self.students.insert("", "end", values=(sid, name, "Present" if sid in marked else "Pending"))
        for row in records:
            self.history.insert("", "end", values=row)
        self.status.set("Data refreshed. Attendance is counted once per student per day.")

    def count_records(self):
        with sqlite3.connect(DB) as connection:
            return connection.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]

    def launch(self, args, label, auto_train=False):
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
        if not (ROOT / "model.yml").exists():
            messagebox.showwarning("Model missing", "Register a student and train the model first.")
            return
        self.launch(["attendance"], "Attendance camera running")

    def stop_camera(self):
        if self.process and self.process.poll() is None:
            if messagebox.askyesno("Stop session", "Stop the current camera session?"):
                self.process.terminate()
                self.status.set("Camera process stopped")
        else:
            self.status.set("Camera is not running")
        self.root.after(800, self.refresh)

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
            shutil.rmtree(ROOT / "faces" / str(int(sid)), ignore_errors=True)
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
