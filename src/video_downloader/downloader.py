from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlparse

from yt_dlp import YoutubeDL


ProgressCallback = Callable[["DownloadProgress"], None]


class DownloadError(RuntimeError):
    """Raised when a video cannot be downloaded."""


@dataclass(frozen=True)
class DownloadOptions:
    output_dir: Path
    overwrite: bool = False
    single_video_only: bool = True


@dataclass(frozen=True)
class DownloadProgress:
    status: str
    message: str
    percent: float | None = None


class YoutubeDLFactory(Protocol):
    def __call__(self, params: dict) -> YoutubeDL:
        ...


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def default_download_dir() -> Path:
    return Path.cwd() / "downloads"


def is_youtube_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() not in YOUTUBE_HOSTS:
        return False
    return bool(parsed.path.strip("/") or parsed.query)


def build_ydl_options(
    options: DownloadOptions,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    ydl_options = {
        # Prefer one ready-to-play MP4 file. This avoids requiring FFmpeg for beginners.
        "format": "best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best",
        "outtmpl": str(options.output_dir / "%(title).200B [%(id)s].%(ext)s"),
        "noplaylist": options.single_video_only,
        "quiet": True,
        "no_warnings": True,
        "windowsfilenames": True,
        "nooverwrites": not options.overwrite,
    }

    if progress_callback is not None:
        ydl_options["progress_hooks"] = [_make_progress_hook(progress_callback)]

    return ydl_options


class YouTubeDownloader:
    def __init__(self, ydl_factory: YoutubeDLFactory = YoutubeDL) -> None:
        self._ydl_factory = ydl_factory

    def download(
        self,
        url: str,
        options: DownloadOptions,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        clean_url = url.strip()
        if not is_youtube_url(clean_url):
            raise DownloadError("Enter a valid YouTube video URL.")

        output_dir = Path(options.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        resolved_options = DownloadOptions(
            output_dir=output_dir,
            overwrite=options.overwrite,
            single_video_only=options.single_video_only,
        )
        ydl_options = build_ydl_options(resolved_options, progress_callback)

        try:
            with self._ydl_factory(ydl_options) as ydl:
                result = ydl.download([clean_url])
        except Exception as exc:
            raise DownloadError(f"Download failed: {exc}") from exc

        if result != 0:
            raise DownloadError("Download failed. Check the URL and try again.")

        if progress_callback is not None:
            progress_callback(
                DownloadProgress(
                    status="complete",
                    message=f"Download complete. Saved in {output_dir}",
                    percent=100.0,
                )
            )


def _make_progress_hook(callback: ProgressCallback) -> Callable[[dict], None]:
    def hook(data: dict) -> None:
        status = data.get("status", "unknown")

        if status == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            percent = (downloaded / total * 100) if total else None
            speed = data.get("_speed_str", "").strip()
            eta = data.get("_eta_str", "").strip()
            parts = ["Downloading"]
            if speed:
                parts.append(speed)
            if eta:
                parts.append(f"ETA {eta}")
            callback(
                DownloadProgress(
                    status="downloading",
                    message=" - ".join(parts),
                    percent=percent,
                )
            )
            return

        if status == "finished":
            callback(
                DownloadProgress(
                    status="processing",
                    message="Download finished. Preparing file...",
                    percent=100.0,
                )
            )
            return

        if status == "error":
            callback(
                DownloadProgress(
                    status="error",
                    message="An error happened during download.",
                    percent=None,
                )
            )

    return hook
