import tempfile
import unittest
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from video_downloader.downloader import (
    DownloadError,
    DownloadOptions,
    DownloadProgress,
    YouTubeDownloader,
    build_ydl_options,
    is_youtube_url,
)


class FakeYoutubeDL:
    last_options = None
    last_urls = None
    result = 0

    def __init__(self, options):
        self.options = options
        FakeYoutubeDL.last_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def download(self, urls):
        FakeYoutubeDL.last_urls = urls
        for hook in self.options.get("progress_hooks", []):
            hook(
                {
                    "status": "downloading",
                    "downloaded_bytes": 50,
                    "total_bytes": 100,
                    "_speed_str": "1.00MiB/s",
                    "_eta_str": "00:01",
                }
            )
            hook({"status": "finished"})
        return FakeYoutubeDL.result


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        FakeYoutubeDL.last_options = None
        FakeYoutubeDL.last_urls = None
        FakeYoutubeDL.result = 0

    def test_accepts_common_youtube_urls(self):
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        ]

        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(is_youtube_url(url))

    def test_rejects_non_youtube_urls(self):
        invalid_urls = [
            "",
            "not a url",
            "ftp://youtube.com/watch?v=abc",
            "https://example.com/watch?v=abc",
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(is_youtube_url(url))

    def test_builds_beginner_friendly_download_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = build_ydl_options(DownloadOptions(output_dir=Path(tmp)))

        self.assertIn("best[ext=mp4]", options["format"])
        self.assertTrue(options["noplaylist"])
        self.assertTrue(options["nooverwrites"])
        self.assertIn("%(title).200B [%(id)s].%(ext)s", options["outtmpl"])

    def test_download_creates_folder_and_reports_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "nested" / "downloads"
            progress_updates = []
            downloader = YouTubeDownloader(ydl_factory=FakeYoutubeDL)

            downloader.download(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                DownloadOptions(output_dir=output_dir),
                progress_callback=progress_updates.append,
            )

            self.assertTrue(output_dir.exists())
            self.assertEqual(FakeYoutubeDL.last_urls, ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
            self.assertIsNotNone(FakeYoutubeDL.last_options)
            self.assertTrue(all(isinstance(item, DownloadProgress) for item in progress_updates))
            self.assertEqual(progress_updates[-1].status, "complete")

    def test_download_rejects_invalid_url_before_calling_ytdlp(self):
        downloader = YouTubeDownloader(ydl_factory=FakeYoutubeDL)

        with self.assertRaises(DownloadError):
            downloader.download("https://example.com/video", DownloadOptions(output_dir=Path(".")))

        self.assertIsNone(FakeYoutubeDL.last_urls)

    def test_download_raises_when_ytdlp_reports_failure(self):
        FakeYoutubeDL.result = 1
        downloader = YouTubeDownloader(ydl_factory=FakeYoutubeDL)

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DownloadError):
                downloader.download(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    DownloadOptions(output_dir=Path(tmp)),
                )


if __name__ == "__main__":
    unittest.main()
