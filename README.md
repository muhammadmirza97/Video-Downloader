# Video Downloader

A beginner-friendly desktop app for downloading YouTube videos into a folder on your computer.

Only download videos that you own, have permission to use, or are allowed to download under YouTube's terms and the video's license.

## Quick Start

### Easiest Way on Windows

Double-click `launch_app.bat`.

It will create a local Python environment, install the required package, and open the app.

### Terminal Way

1. Open a terminal in this folder.
2. Create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install the required package:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Start the app:

   ```powershell
   python run_app.py
   ```

5. Paste a YouTube URL, choose a folder, and click **Download MP4**.

By default, videos are saved into the `downloads` folder in this project.

## Project Structure

```text
.
├── run_app.py
├── requirements.txt
├── src/
│   └── video_downloader/
│       ├── app.py
│       ├── downloader.py
│       └── gui.py
└── tests/
    └── test_downloader.py
```

## Run Tests

```powershell
python -m unittest discover -s tests
```

The tests check the downloader logic without downloading real videos, so they run quickly and safely.
