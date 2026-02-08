import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import re

# ================== НАСТРОЙКИ ==================

ROOT_DIR = __import__("os").path.dirname(__file__)
FRONT_DIR = __import__("os").path.join(ROOT_DIR, "frontend")
BACK_DIR = __import__("os").path.join(ROOT_DIR, "backend")

COMMANDS = [
    {"title": "Frontend (npm run dev)", "cmd": ["cmd", "/k", "npm run dev"], "cwd": FRONT_DIR},
    {"title": "Auth service",           "cmd": ["cmd", "/k", "run_auth.bat"], "cwd": BACK_DIR},
    {"title": "Worker",                "cmd": ["cmd", "/k", "run_worker.bat"], "cwd": BACK_DIR},
    {"title": "Main API",              "cmd": ["cmd", "/k", "run_main.bat"], "cwd": BACK_DIR},
]

# ==============================================

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Базовые ANSI цвета (30-37) + bright (90-97)
ANSI_FG = {
    30: "#000000", 31: "#cc0000", 32: "#00cc00", 33: "#cccc00",
    34: "#3366ff", 35: "#cc00cc", 36: "#00cccc", 37: "#e6e6e6",
    90: "#777777", 91: "#ff4444", 92: "#44ff44", 93: "#ffff44",
    94: "#6699ff", 95: "#ff66ff", 96: "#66ffff", 97: "#ffffff",
}


class ConsoleFrame(tk.Frame):
    def __init__(self, master, title: str):
        super().__init__(master, bd=0, highlightthickness=0, bg=master["bg"])

        self.label = tk.Label(
            self,
            text=title,
            anchor="center",
            font=("Segoe UI", 10, "bold"),
            bg=master["bg"],
            fg="#111111",
            padx=2,
            pady=2,
        )
        self.label.pack(fill="x")

        body = tk.Frame(self, bd=0, highlightthickness=0, bg="#0e0e0e")
        body.pack(fill="both", expand=True)

        self.text = tk.Text(
            body,
            bg="#0e0e0e",
            fg="#e6e6e6",
            insertbackground="white",
            font=("Consolas", 9),
            wrap="none",
            bd=0,
            highlightthickness=0,
        )
        self.text.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(body, command=self.text.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=self.scrollbar.set)

        # ---- ANSI state ----
        self._cur_tag = "fg_default"
        self.text.tag_configure("fg_default", foreground="#e6e6e6")
        for code, color in ANSI_FG.items():
            self.text.tag_configure(f"fg_{code}", foreground=color)

        # ---- Copy / Select / Context menu ----
        self.text.bind("<Control-c>", self._copy)
        self.text.bind("<Control-C>", self._copy)
        self.text.bind("<Control-a>", self._select_all)
        self.text.bind("<Control-A>", self._select_all)

        # ПКМ (Windows)
        self.text.bind("<Button-3>", self._context_menu)

        # Контекстное меню (создадим один раз)
        self._menu = tk.Menu(self.text, tearoff=0)
        self._menu.add_command(label="Copy", command=self._copy)
        self._menu.add_command(label="Select all", command=self._select_all)

    def _copy(self, event=None):
        try:
            sel = self.text.get("sel.first", "sel.last")
            self.text.clipboard_clear()
            self.text.clipboard_append(sel)
        except tk.TclError:
            pass
        return "break"

    def _select_all(self, event=None):
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "1.0")
        self.text.see("insert")
        return "break"

    def _context_menu(self, event):
        # Обновим состояние пунктов (если нет выделения — Copy можно оставить, просто ничего не скопирует)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()
        return "break"

    def _apply_ansi_codes(self, codes: list[int]):
        # reset
        if 0 in codes or not codes:
            self._cur_tag = "fg_default"
            return

        # ищем первый fg-код из поддерживаемых
        for c in codes:
            if c in ANSI_FG:
                self._cur_tag = f"fg_{c}"
                return

    def write(self, chunk: str):
        """Пишет текст с поддержкой ANSI-цветов вида: \x1b[32m ... \x1b[0m"""
        if not chunk:
            return

        pos = 0
        for m in ANSI_RE.finditer(chunk):
            # обычный текст до ANSI
            if m.start() > pos:
                s = chunk[pos:m.start()]
                self.text.insert("end", s, (self._cur_tag,))

            # ANSI
            seq = m.group()             # "\x1b[...m"
            inside = seq[2:-1].lstrip("[")
            codes = []
            if inside.strip():
                try:
                    codes = [int(x) for x in inside.split(";") if x.strip().isdigit()]
                except Exception:
                    codes = []
            self._apply_ansi_codes(codes)
            pos = m.end()

        # хвост
        if pos < len(chunk):
            self.text.insert("end", chunk[pos:], (self._cur_tag,))

        self.text.see("end")


def run_process(console: ConsoleFrame, cmd, cwd):
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        for line in proc.stdout:
            # Писать в Tkinter только из главного потока
            console.after(0, console.write, line)

    except Exception as e:
        console.after(0, console.write, f"\n[ERROR] {e}\n")


def main():
    root = tk.Tk()
    root.title("TG Web Auth Launcher")
    root.geometry("1200x800")
    root.configure(bg="#f2f2f2")

    root.grid_rowconfigure((0, 1), weight=1)
    root.grid_columnconfigure((0, 1), weight=1)

    consoles = []
    for i, cfg in enumerate(COMMANDS):
        frame = ConsoleFrame(root, cfg["title"])
        frame.grid(
            row=i // 2,
            column=i % 2,
            sticky="nsew",
            padx=1,
            pady=1,
        )
        consoles.append((frame, cfg))

    def start_all():
        for console, cfg in consoles:
            t = threading.Thread(
                target=run_process,
                args=(console, cfg["cmd"], cfg["cwd"]),
                daemon=True,
            )
            t.start()

    root.after(200, start_all)
    root.mainloop()


if __name__ == "__main__":
    main()
