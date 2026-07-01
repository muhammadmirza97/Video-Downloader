from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from video_downloader.downloader import (
    DownloadError,
    DownloadOptions,
    DownloadProgress,
    YouTubeDownloader,
    default_download_dir,
    is_youtube_url,
)


class DownloaderApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=24)
        self.master = master
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.downloader = YouTubeDownloader()

        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(default_download_dir()))
        self.status_var = tk.StringVar(value="Paste a YouTube URL to begin.")
        self.progress_var = tk.DoubleVar(value=0)

        self._build_ui()
        self._poll_events()

    def _build_ui(self) -> None:
        self.master.title("Video Downloader")
        self.master.minsize(720, 520)
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text="YouTube Video Downloader", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            self,
            text="Paste a video link, choose where to save it, then click Download MP4.",
            style="Subtitle.TLabel",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 20))

        safety = ttk.Label(
            self,
            text="Only download videos you own, have permission to use, or are allowed to download.",
            style="Safety.TLabel",
        )
        safety.grid(row=2, column=0, sticky="w", pady=(0, 16))

        url_frame = ttk.LabelFrame(self, text="1. YouTube video link", padding=12)
        url_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        url_frame.columnconfigure(0, weight=1)

        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var)
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.focus_set()

        folder_frame = ttk.LabelFrame(self, text="2. Save video into this folder", padding=12)
        folder_frame.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        folder_frame.columnconfigure(0, weight=1)

        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var)
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        browse_button = ttk.Button(folder_frame, text="Browse...", command=self._choose_folder)
        browse_button.grid(row=0, column=1)

        action_frame = ttk.Frame(self)
        action_frame.grid(row=5, column=0, sticky="ew", pady=(4, 16))
        action_frame.columnconfigure(2, weight=1)

        self.download_button = ttk.Button(
            action_frame,
            text="Download MP4",
            command=self._start_download,
            style="Accent.TButton",
        )
        self.download_button.grid(row=0, column=0, padx=(0, 8))

        open_button = ttk.Button(action_frame, text="Open Folder", command=self._open_folder)
        open_button.grid(row=0, column=1)

        self.progress_bar = ttk.Progressbar(
            self,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.grid(row=6, column=0, sticky="ew")

        status = ttk.Label(self, textvariable=self.status_var)
        status.grid(row=7, column=0, sticky="w", pady=(8, 16))

        log_frame = ttk.LabelFrame(self, text="Download details", padding=12)
        log_frame.grid(row=8, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.rowconfigure(8, weight=1)

        self.log_text = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.cwd()))
        if folder:
            self.folder_var.set(folder)

    def _open_folder(self) -> None:
        folder = Path(self.folder_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _start_download(self) -> None:
        url = self.url_var.get().strip()
        if not is_youtube_url(url):
            messagebox.showerror("Check the link", "Paste a valid YouTube video URL first.")
            self.url_entry.focus_set()
            return

        folder = Path(self.folder_var.get()).expanduser()
        self.progress_var.set(0)
        self.status_var.set("Starting download...")
        self._append_log(f"URL: {url}")
        self._append_log(f"Folder: {folder}")
        self._set_downloading(True)

        thread = threading.Thread(
            target=self._download_worker,
            args=(url, folder),
            daemon=True,
        )
        thread.start()

    def _download_worker(self, url: str, folder: Path) -> None:
        def progress(progress_update: DownloadProgress) -> None:
            self.events.put(("progress", progress_update))

        try:
            self.downloader.download(
                url,
                DownloadOptions(output_dir=folder),
                progress_callback=progress,
            )
        except DownloadError as exc:
            self.events.put(("error", str(exc)))
        else:
            self.events.put(("done", "Download complete."))

    def _poll_events(self) -> None:
        while True:
            try:
                event_type, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if event_type == "progress":
                self._handle_progress(payload)
            elif event_type == "error":
                self._set_downloading(False)
                self.status_var.set(str(payload))
                self._append_log(str(payload))
                messagebox.showerror("Download failed", str(payload))
            elif event_type == "done":
                self._set_downloading(False)
                self.progress_var.set(100)
                self.status_var.set(str(payload))
                self._append_log(str(payload))
                messagebox.showinfo("Finished", str(payload))

        self.after(100, self._poll_events)

    def _handle_progress(self, payload: object) -> None:
        progress = payload
        if not isinstance(progress, DownloadProgress):
            return
        if progress.percent is not None:
            self.progress_var.set(max(0, min(100, progress.percent)))
        self.status_var.set(progress.message)
        self._append_log(progress.message)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_downloading(self, is_downloading: bool) -> None:
        state = "disabled" if is_downloading else "normal"
        self.download_button.configure(state=state)
        self.url_entry.configure(state=state)
        self.folder_entry.configure(state=state)


def run_gui() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
    style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
    style.configure("Safety.TLabel", font=("Segoe UI", 9), foreground="#7a4a00")
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
    DownloaderApp(root)
    root.mainloop()
