"""Student profile editor: optional contact/class details stored locally only."""
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
DB = ROOT / "attendance.db"
FACES = ROOT / "faces"
BG = "#0b1220"
PANEL = "#172338"
FG = "#f1f5fa"
MUTED = "#a6bad1"
ACCENT = "#40bfae"


def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS student_profiles (
        student_id INTEGER PRIMARY KEY,
        class_name TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        registered_on TEXT NOT NULL DEFAULT (date('now'))
    )""")
    connection.commit()


def open_profile(parent, student_id, on_save=None):
    """Open an existing student's details, face thumbnail and attendance history."""
    with sqlite3.connect(DB) as connection:
        ensure_schema(connection)
        student = connection.execute(
            "SELECT id, name FROM students WHERE id=?", (student_id,)).fetchone()
        if not student:
            messagebox.showerror("Not found", "Student no longer exists.", parent=parent)
            return
        info = connection.execute(
            "SELECT class_name, phone, registered_on FROM student_profiles WHERE student_id=?",
            (student_id,)).fetchone()
        records = connection.execute(
            "SELECT date,time FROM attendance WHERE student_id=? ORDER BY date DESC LIMIT 300",
            (student_id,)).fetchall()

    dialog = tk.Toplevel(parent)
    dialog.title(f"Student Profile - {student[1]}")
    dialog.geometry("590x650")
    dialog.minsize(480, 520)
    dialog.configure(bg=BG)
    dialog.transient(parent)
    dialog.grab_set()
    main = tk.Frame(dialog, bg=BG, padx=24, pady=16)
    main.pack(fill="both", expand=True)

    tk.Label(main, text="STUDENT PROFILE", fg=ACCENT, bg=BG,
             font=("Segoe UI", 11, "bold")).pack(anchor="w")
    tk.Label(main, text=f"Student ID: {student_id}", bg=BG, fg=FG,
             font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(4, 12))

    photo_path = FACES / str(student_id) / "000.png"
    if not photo_path.exists():
        photos = sorted((FACES / str(student_id)).glob("*.png"))
        photo_path = photos[0] if photos else None
    if photo_path:
        try:
            with Image.open(photo_path) as source:
                image = source.convert("RGB")
                image.thumbnail((130, 130))
                photo = ImageTk.PhotoImage(image)
            photo_label = tk.Label(main, image=photo, bg=BG)
            photo_label.image = photo
            photo_label.pack(anchor="w", pady=(0, 10))
        except (OSError, ValueError):
            pass

    fields = {}
    for label, value, key in [
        ("Full name", student[1], "name"),
        ("Class / group", info[0] if info else "", "class_name"),
        ("Phone (optional)", info[1] if info else "", "phone"),
    ]:
        tk.Label(main, text=label, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 2))
        entry = tk.Entry(main, font=("Segoe UI", 11))
        entry.insert(0, value)
        entry.pack(fill="x", ipady=5)
        fields[key] = entry
    tk.Label(main, text=f"Profile created: {info[2] if info else 'Not recorded (legacy student)'}",
             bg=BG, fg=MUTED).pack(anchor="w", pady=(10, 8))

    def save():
        name = " ".join(fields["name"].get().split())
        group = fields["class_name"].get().strip()
        phone = fields["phone"].get().strip()
        if not name or len(name) > 100 or len(group) > 100 or len(phone) > 40:
            messagebox.showwarning("Invalid input", "Check name, class and phone lengths.",
                                   parent=dialog)
            return
        try:
            with sqlite3.connect(DB) as connection:
                duplicates = connection.execute(
                    "SELECT name FROM students WHERE id<>?", (student_id,)).fetchall()
                if any(" ".join(n.split()).casefold() == name.casefold()
                       for (n,) in duplicates):
                    messagebox.showwarning("Duplicate name", "This name is already registered.",
                                           parent=dialog)
                    return
                connection.execute("UPDATE students SET name=? WHERE id=?",
                                   (name, student_id))
                connection.execute("""INSERT INTO student_profiles(student_id,class_name,phone)
                    VALUES(?,?,?) ON CONFLICT(student_id) DO UPDATE SET
                    class_name=excluded.class_name,phone=excluded.phone""",
                    (student_id, group, phone))
            dialog.destroy()
            if on_save:
                on_save()
        except sqlite3.Error as exc:
            messagebox.showerror("Save failed", str(exc), parent=dialog)

    tk.Button(main, text="Save Profile", command=save, bg=ACCENT, fg=BG,
              font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=7).pack(
                  anchor="w", pady=(5, 12))

    tk.Label(main, text=f"Attendance History ({len(records)} recent records)", bg=BG,
             fg=FG, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(5, 7))
    history = ttk.Treeview(main, columns=("date", "time"), show="headings", height=5)
    history.heading("date", text="Date")
    history.heading("time", text="Time")
    for record in records:
        history.insert("", "end", values=record)
    history.pack(fill="both", expand=True)
