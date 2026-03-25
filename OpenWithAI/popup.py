import ctypes
from ctypes import wintypes
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import browser
from app_runtime import get_logger, log_exception
from history import add_to_history
from settings import load_settings, save_settings

logger = get_logger()

CF_HDROP = 15
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.restype = ctypes.c_void_p
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


BG_ROOT = "#EEF3F7"
BG_CARD = "#FCFAF4"
BG_ACCENT = "#0D5C63"
BG_ACCENT_HOVER = "#114E55"
BG_ACCENT_SOFT = "#D8F0EC"
BG_MUTED = "#E6EEF2"
BG_ACTION = "#DCE8F2"
BG_SECONDARY = "#F4B860"
BG_SECONDARY_HOVER = "#E6A94A"
FG_TITLE = "#183247"
FG_BODY = "#31475A"
FG_MUTED = "#5E7488"
FG_SUCCESS = "#166534"
FG_WARNING = "#B45309"
FG_DANGER = "#B91C1C"
BORDER = "#C8D6E3"
FONT_TITLE = ("Bahnschrift SemiBold", 20)
FONT_SUBTITLE = ("Segoe UI", 10)
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BUTTON = ("Bahnschrift SemiBold", 11)


def dedupe_paths(paths):
    seen = set()
    result = []
    for path in paths:
        if not isinstance(path, str):
            continue
        clean = path.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def format_bytes(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size)} B"


def split_file_name(path):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    return name, ext[1:].upper() if ext else "FILE"


def get_file_stats(paths):
    existing = [path for path in paths if os.path.isfile(path)]
    missing = [path for path in paths if not os.path.isfile(path)]
    total_size = 0
    for path in existing:
        try:
            total_size += os.path.getsize(path)
        except OSError:
            logger.warning("Could not read size for %s", path)
    return existing, missing, total_size


def get_suggested_ai(file_list):
    del file_list
    return load_settings().get("default_ai", "Claude")


def _set_clipboard_blob(format_id, payload):
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        raise OSError("GlobalAlloc failed")

    locked = kernel32.GlobalLock(handle)
    if not locked:
        kernel32.GlobalFree(handle)
        raise OSError("GlobalLock failed")

    try:
        ctypes.memmove(locked, payload, len(payload))
    finally:
        kernel32.GlobalUnlock(handle)

    if not user32.SetClipboardData(format_id, handle):
        kernel32.GlobalFree(handle)
        raise OSError(f"SetClipboardData failed for format {format_id}")


def set_windows_file_clipboard(paths, retries=15, retry_delay=0.08):
    existing_paths = [os.path.abspath(path) for path in dedupe_paths(paths) if os.path.isfile(path)]
    if not existing_paths:
        return False, []

    dropfiles = DROPFILES()
    dropfiles.pFiles = ctypes.sizeof(DROPFILES)
    dropfiles.fWide = True

    dropfiles_bytes = ctypes.string_at(ctypes.byref(dropfiles), ctypes.sizeof(dropfiles))
    file_payload = ("\0".join(existing_paths) + "\0\0").encode("utf-16le")
    text_payload = ("\r\n".join(existing_paths) + "\0").encode("utf-16le")

    opened = False
    for _ in range(retries):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(retry_delay)
    if not opened:
        raise OSError("OpenClipboard failed")

    try:
        if not user32.EmptyClipboard():
            raise OSError("EmptyClipboard failed")
        _set_clipboard_blob(CF_HDROP, dropfiles_bytes + file_payload)
        _set_clipboard_blob(CF_UNICODETEXT, text_payload)
    finally:
        user32.CloseClipboard()

    return True, existing_paths


class PopupUI(tk.Tk):
    def __init__(self, file_paths):
        super().__init__()

        self.title("Open with AI")
        self.geometry("980x680")
        self.minsize(900, 620)
        self.configure(bg=BG_ROOT)
        self.file_list = dedupe_paths(file_paths)
        self.settings = load_settings()
        self.browsers = browser.get_installed_browsers(self.settings)
        self.ais = browser.get_available_ais(self.settings)
        self.status_var = tk.StringVar(value="Pick your target, then open the AI page and paste with Ctrl+V.")
        self.summary_var = tk.StringVar()
        self.clipboard_hint_var = tk.StringVar()
        self.item_to_path = {}
        self.status_label = None
        self.launch_button = None

        self._configure_style()
        self._create_widgets()
        self.refresh_choices()
        self.refresh_file_table()
        self.bind("<Delete>", lambda event: self.remove_selected())

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("OWA.TFrame", background=BG_CARD)
        style.configure("OWA.TLabelframe", background=BG_CARD, bordercolor=BORDER, relief="solid")
        style.configure("OWA.TLabelframe.Label", background=BG_CARD, foreground=FG_TITLE, font=FONT_BODY)
        style.configure("OWA.Treeview", background=BG_CARD, fieldbackground=BG_CARD, foreground=FG_BODY, bordercolor=BORDER, rowheight=28, font=FONT_BODY)
        style.configure("OWA.Treeview.Heading", background=BG_MUTED, foreground=FG_TITLE, font=FONT_BUTTON, relief="flat")
        style.map("OWA.Treeview", background=[("selected", BG_ACCENT)], foreground=[("selected", "#FFFFFF")])
        style.configure("OWA.TCombobox", fieldbackground=BG_CARD, background=BG_CARD, foreground=FG_BODY, arrowsize=14)

    def _create_widgets(self):
        shell = tk.Frame(self, bg=BG_ROOT)
        shell.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        header = tk.Frame(shell, bg=BG_ROOT)
        header.pack(fill=tk.X, pady=(0, 18))

        tk.Label(header, text="Open with AI", bg=BG_ROOT, fg=FG_TITLE, font=FONT_TITLE).pack(anchor=tk.W)
        tk.Label(
            header,
            text="Files stay exactly as they are. We open the AI site and copy the selected files to the Windows clipboard so you can paste or upload them directly.",
            bg=BG_ROOT,
            fg=FG_MUTED,
            font=FONT_SUBTITLE,
            justify=tk.LEFT,
            wraplength=900,
        ).pack(anchor=tk.W, pady=(6, 0))

        summary_card = tk.Frame(shell, bg=BG_ACCENT_SOFT, highlightbackground=BORDER, highlightthickness=1)
        summary_card.pack(fill=tk.X, pady=(0, 18))
        tk.Label(summary_card, textvariable=self.summary_var, bg=BG_ACCENT_SOFT, fg=FG_TITLE, font=FONT_BUTTON).pack(anchor=tk.W, padx=16, pady=(12, 4))
        tk.Label(summary_card, textvariable=self.clipboard_hint_var, bg=BG_ACCENT_SOFT, fg=FG_BODY, font=FONT_SMALL, justify=tk.LEFT, wraplength=900).pack(anchor=tk.W, padx=16, pady=(0, 12))

        content = tk.Frame(shell, bg=BG_ROOT)
        content.pack(fill=tk.BOTH, expand=True)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        files_card = tk.Frame(content, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        files_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        settings_card = tk.Frame(content, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        settings_card.grid(row=0, column=1, sticky="nsew")

        files_header = tk.Frame(files_card, bg=BG_CARD)
        files_header.pack(fill=tk.X, padx=18, pady=(18, 10))
        tk.Label(files_header, text="Selected Files", bg=BG_CARD, fg=FG_TITLE, font=("Segoe UI Semibold", 12)).pack(anchor=tk.W)
        tk.Label(files_header, text="You can add more files, remove selections, and review what will be copied.", bg=BG_CARD, fg=FG_MUTED, font=FONT_SMALL).pack(anchor=tk.W, pady=(4, 0))

        actions = tk.Frame(files_card, bg=BG_CARD)
        actions.pack(fill=tk.X, padx=18, pady=(0, 12))
        self._make_secondary_button(actions, "Add Files", self.add_files).pack(side=tk.LEFT)
        self._make_secondary_button(actions, "Remove Selected", self.remove_selected).pack(side=tk.LEFT, padx=(8, 0))
        self._make_secondary_button(actions, "Remove Missing", self.remove_missing).pack(side=tk.LEFT, padx=(8, 0))

        tree_frame = tk.Frame(files_card, bg=BG_CARD)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))
        columns = ("name", "type", "size", "folder", "status")
        self.file_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style="OWA.Treeview")
        headings = {
            "name": ("Name", 220),
            "type": ("Type", 80),
            "size": ("Size", 90),
            "folder": ("Folder", 220),
            "status": ("Status", 90),
        }
        for key, (label, width) in headings.items():
            self.file_tree.heading(key, text=label)
            self.file_tree.column(key, width=width, anchor=tk.W, stretch=(key in {"name", "folder"}))
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        self.file_tree.tag_configure("missing", foreground=FG_DANGER)
        self.file_tree.tag_configure("ready", foreground=FG_BODY)

        settings_header = tk.Frame(settings_card, bg=BG_CARD)
        settings_header.pack(fill=tk.X, padx=18, pady=(18, 10))
        tk.Label(settings_header, text="Route and Launch", bg=BG_CARD, fg=FG_TITLE, font=("Segoe UI Semibold", 12)).pack(anchor=tk.W)
        tk.Label(settings_header, text="Choose where to open the chat and how you want to keep using this tool.", bg=BG_CARD, fg=FG_MUTED, font=FONT_SMALL).pack(anchor=tk.W, pady=(4, 0))

        prefs = tk.Frame(settings_card, bg=BG_CARD)
        prefs.pack(fill=tk.X, padx=18, pady=(0, 12))

        self._label(prefs, "Browser").pack(anchor=tk.W)
        self.brw_var = tk.StringVar(value=self.settings.get("default_browser", "System Default"))
        self.brw_combo = ttk.Combobox(prefs, textvariable=self.brw_var, state="readonly", style="OWA.TCombobox")
        self.brw_combo.pack(fill=tk.X, pady=(6, 14))

        self._label(prefs, "AI destination").pack(anchor=tk.W)
        self.ai_var = tk.StringVar(value=get_suggested_ai(self.file_list))
        self.ai_combo = ttk.Combobox(prefs, textvariable=self.ai_var, state="readonly", style="OWA.TCombobox")
        self.ai_combo.pack(fill=tk.X, pady=(6, 14))

        custom_row = tk.Frame(prefs, bg=BG_CARD)
        custom_row.pack(fill=tk.X, pady=(0, 14))
        self._make_secondary_button(custom_row, "Add Custom AI", self.add_custom_ai).pack(side=tk.LEFT)
        self._make_secondary_button(custom_row, "Add Custom Browser", self.add_custom_browser).pack(side=tk.LEFT, padx=(8, 0))

        launch_panel = tk.Frame(settings_card, bg=BG_CARD)
        launch_panel.pack(fill=tk.X, padx=18, pady=(0, 16))
        self.launch_button = self._make_primary_button(launch_panel, "Confirm and Open in Browser", self.open_ai)
        self.launch_button.pack(fill=tk.X)
        tk.Label(
            launch_panel,
            text="This opens the selected AI in your browser and copies the chosen files so you can paste them with Ctrl+V.",
            bg=BG_CARD,
            fg=FG_MUTED,
            font=FONT_SMALL,
            justify=tk.LEFT,
            wraplength=320,
        ).pack(anchor=tk.W, pady=(8, 0))

        tips = tk.Frame(settings_card, bg=BG_MUTED, highlightbackground=BORDER, highlightthickness=1)
        tips.pack(fill=tk.X, padx=18, pady=(0, 16))
        tk.Label(tips, text="How This Works", bg=BG_MUTED, fg=FG_TITLE, font=FONT_BUTTON).pack(anchor=tk.W, padx=14, pady=(12, 6))
        tk.Label(
            tips,
            text="1. Click the main button.\n2. The chosen AI page opens in your browser.\n3. Click the chat or upload area and press Ctrl+V.\n4. If the site blocks pasted files, use its attach button or drag-and-drop.",
            bg=BG_MUTED,
            fg=FG_BODY,
            font=FONT_SMALL,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=14, pady=(0, 12))

        status_panel = tk.Frame(settings_card, bg=BG_ACCENT_SOFT, highlightbackground=BORDER, highlightthickness=1)
        status_panel.pack(fill=tk.X, padx=18, pady=(0, 18))
        self.status_label = tk.Label(
            status_panel,
            textvariable=self.status_var,
            bg=BG_ACCENT_SOFT,
            fg=FG_MUTED,
            font=FONT_SMALL,
            justify=tk.LEFT,
            wraplength=320,
        )
        self.status_label.pack(anchor=tk.W, padx=14, pady=14)

    def _label(self, parent, text):
        return tk.Label(parent, text=text, bg=BG_CARD, fg=FG_TITLE, font=FONT_BUTTON)

    def _make_primary_button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BG_ACCENT,
            fg="#FFFFFF",
            activebackground=BG_ACCENT_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            bd=0,
            padx=20,
            pady=12,
            cursor="hand2",
            font=FONT_BUTTON,
        )

    def _make_secondary_button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BG_SECONDARY,
            fg=FG_TITLE,
            activebackground=BG_SECONDARY_HOVER,
            activeforeground=FG_TITLE,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=9,
            cursor="hand2",
            font=FONT_BODY,
        )

    def set_status(self, message, tone="muted"):
        self.status_var.set(message)
        color = FG_MUTED
        if tone == "success":
            color = FG_SUCCESS
        elif tone == "warning":
            color = FG_WARNING
        elif tone == "danger":
            color = FG_DANGER
        if self.status_label is not None:
            self.status_label.configure(fg=color)

    def refresh_choices(self):
        self.settings = load_settings()
        self.browsers = browser.get_installed_browsers(self.settings)
        self.ais = browser.get_available_ais(self.settings)

        browser_default = self.settings.get("default_browser", self.browsers[0])
        ai_default = self.settings.get("default_ai", self.ais[0])
        self.brw_combo["values"] = self.browsers
        self.ai_combo["values"] = self.ais
        self.brw_var.set(browser_default if browser_default in self.browsers else self.browsers[0])
        self.ai_var.set(ai_default if ai_default in self.ais else self.ais[0])

    def refresh_file_table(self):
        self.file_list = dedupe_paths(self.file_list)
        self.item_to_path = {}
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        existing_files, missing_files, total_size = get_file_stats(self.file_list)
        for path in self.file_list:
            name, file_type = split_file_name(path)
            folder = os.path.dirname(path) or "."
            if os.path.isfile(path):
                try:
                    size_text = format_bytes(os.path.getsize(path))
                except OSError:
                    size_text = "Unknown"
                status = "Ready"
                tag = "ready"
            else:
                size_text = "-"
                status = "Missing"
                tag = "missing"
            item_id = self.file_tree.insert("", tk.END, values=(name, file_type, size_text, folder, status), tags=(tag,))
            self.item_to_path[item_id] = path

        count_text = f"{len(existing_files)} ready"
        if missing_files:
            count_text += f" • {len(missing_files)} missing"
        count_text += f" • {len(self.file_list)} total selected"
        self.summary_var.set(f"{count_text} • {format_bytes(total_size)}")
        self.clipboard_hint_var.set("All file types are kept intact. Large batches are fine as long as Windows Explorer invokes the command and the AI site supports the upload size.")

        if existing_files:
            self.set_status("Ready to launch. The selected files will be copied as real files for Ctrl+V.", "success")
        elif self.file_list:
            self.set_status("The current selection contains only missing items. Remove them or add fresh files.", "warning")
        else:
            self.set_status("No files selected yet. Add files or trigger the popup from Explorer.", "warning")

    def add_files(self):
        picked = filedialog.askopenfilenames(title="Add files", filetypes=[("All files", "*.*")], parent=self)
        if not picked:
            return
        self.file_list.extend(picked)
        self.refresh_file_table()

    def add_custom_ai(self):
        name = simpledialog.askstring("Custom AI", "AI name (example: Perplexity):", parent=self)
        if not name:
            return
        url = simpledialog.askstring("Custom AI", "AI URL (https recommended):", parent=self)
        if not url:
            return

        name = browser.normalize_choice_name(name, "")
        if not name:
            messagebox.showerror("Custom AI", "Please enter a valid AI name.", parent=self)
            return
        url = url.strip()
        if not browser.is_safe_ai_url(url):
            messagebox.showerror("Custom AI", "Use an https URL, or http only for localhost.", parent=self)
            return

        custom = self.settings.get("custom_ai_urls", {})
        custom[name] = url
        self.settings["custom_ai_urls"] = custom
        self.settings = save_settings(self.settings)
        self.refresh_choices()
        self.set_status(f"Saved custom AI '{name}'.", "success")

    def add_custom_browser(self):
        name = simpledialog.askstring("Custom Browser", "Browser name (example: Opera):", parent=self)
        if not name:
            return
        exe_path = filedialog.askopenfilename(
            title="Select browser executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
            parent=self,
        )
        if not exe_path:
            return

        name = browser.normalize_choice_name(name, "")
        if not name:
            messagebox.showerror("Custom Browser", "Please enter a valid browser name.", parent=self)
            return
        if not browser.is_valid_browser_path(exe_path):
            messagebox.showerror("Custom Browser", "Please select a valid browser executable (.exe).", parent=self)
            return

        custom = self.settings.get("custom_browsers", {})
        custom[name] = exe_path
        self.settings["custom_browsers"] = custom
        self.settings = save_settings(self.settings)
        self.refresh_choices()
        self.set_status(f"Saved custom browser '{name}'.", "success")

    def remove_selected(self):
        selected = self.file_tree.selection()
        if not selected:
            self.set_status("Select one or more rows to remove them from this batch.", "warning")
            return
        selected_paths = {self.item_to_path[item_id] for item_id in selected if item_id in self.item_to_path}
        self.file_list = [path for path in self.file_list if path not in selected_paths]
        self.refresh_file_table()

    def remove_missing(self):
        before = len(self.file_list)
        self.file_list = [path for path in self.file_list if os.path.isfile(path)]
        removed = before - len(self.file_list)
        self.refresh_file_table()
        if removed:
            self.set_status(f"Removed {removed} missing item(s) from the batch.", "success")
        else:
            self.set_status("There were no missing items to remove.", "warning")

    def open_ai(self):
        self.settings["default_browser"] = self.brw_var.get()
        self.settings["default_ai"] = self.ai_var.get()
        self.settings = save_settings(self.settings)

        existing_files, missing_files, total_size = get_file_stats(self.file_list)
        if not existing_files:
            messagebox.showwarning("Open with AI", "No existing files are selected right now.", parent=self)
            return

        clipboard_ok = False
        clipboard_files = []
        try:
            clipboard_ok, clipboard_files = set_windows_file_clipboard(existing_files)
        except Exception as exc:
            log_exception("Failed to copy files to the Windows clipboard.", exc)

        launched = browser.launch_ai(self.brw_var.get(), self.ai_var.get(), self.settings.get("custom_ai_urls", {}), existing_files)
        if not launched:
            messagebox.showerror("Open with AI", "The selected AI page could not be opened in that browser.", parent=self)
            return

        if clipboard_files:
            add_to_history(clipboard_files, self.ai_var.get())

        self.withdraw()
        details = [
            f"Opened {self.ai_var.get()} in {self.brw_var.get()}.",
            f"Batch size: {len(existing_files)} file(s) • {format_bytes(total_size)}",
        ]
        if clipboard_ok and clipboard_files:
            details.append("The files are on your Windows clipboard as real files. Click the chat or upload area and press Ctrl+V.")
        else:
            details.append("The AI page opened, but the clipboard could not hold the files. Use the site's attach button or drag-and-drop instead.")
        if missing_files:
            details.append(f"Skipped missing item(s): {len(missing_files)}")

        messagebox.showinfo("Open with AI", "\n\n".join(details), parent=self)
        self.destroy()


def show_popup(file_paths):
    app = PopupUI(file_paths)
    app.mainloop()

