# AVI to MP4 Converter

A batch converter that turns every AVI file in a folder into MP4. Built with Python and FFmpeg.

---

## Requirements

- **Python 3.10 or newer** — required for the `str | None` type hint syntax
- **FFmpeg** — the tool that does the actual encoding

You do not need to install any extra Python packages. Everything used (`tkinter`, `subprocess`, `threading`, `pathlib`) ships with Python.

---

## Installing FFmpeg

If you do not already have FFmpeg, the easiest way on Windows is via Winget:

```
winget install Gyan.FFmpeg
```

Then add the `bin` folder to your PATH, or just place `ffmpeg.exe` in the same folder as this project and it will be picked up automatically.

---

## How to Run

Open a terminal in the project folder and run:

```
python main.py
```

That is it. The GUI will open.

---

## Using the App

1. Click **Browse** next to *Input Folder* and select the folder containing your AVI files.
   The file list will populate automatically after you pick a folder.

2. Optionally set an *Output Folder*. If left blank, the MP4 files are saved into the same folder as the originals.

3. Pick a quality preset:
   | Preset | CRF | Notes |
   |---|---|---|
   | Lossless | 0 | Very large files. Use only if you need byte-perfect quality. |
   | High | 18 | Default. Visually near-lossless for most content. |
   | Medium | 23 | FFmpeg's own default. Good balance of size and quality. |
   | Low | 28 | Smaller files, noticeable quality loss on complex scenes. |

4. Tick **Delete original AVI after conversion** if you want the source files removed on success.

5. Click **Convert All** to start. A per-file progress bar and an overall bar track the job.
   Click **Stop** at any time — the current file finishes before the process halts.

---

## Output Format

| Property | Value |
|---|---|
| Container | MP4 |
| Video codec | H.264 (libx264) |
| Audio codec | AAC |
| Audio bitrate | 192 kbps |
| Pixel format | yuv420p |

`yuv420p` is forced explicitly because some AVI files contain pixel formats (`bgr24`, `yuv410p`, etc.) that libx264 refuses to encode without it.

`+faststart` is applied so the MP4 metadata sits at the start of the file, which lets video players and browsers begin playback before the file fully downloads.

---

## Project Structure

```
AVICONVERTER/
├── main.py          Entry point — run this
├── app.py           Main window, all UI layout and event handling
├── ffmpeg_utils.py  FFmpeg detection and subprocess conversion logic
├── theme.py         Color palette and font constants
└── README.md        This file
```

If you want to change how the app looks, edit `theme.py`.
If you want to adjust the FFmpeg command or add new output options, edit `ffmpeg_utils.py`.

---

## Troubleshooting

**"FFmpeg not found" warning on startup**
The app checks three locations in order: the project folder, your system PATH, and a known WinGet install path. If none of those match your setup, either add FFmpeg to PATH or drop `ffmpeg.exe` directly into the project folder.

**A file fails with an error message in the status bar**
The exact last line from FFmpeg's stderr is shown. The most common cause is a corrupted or incomplete AVI file. You can also try opening the file in another player first to confirm it is playable.

**The app window is blank or crashes on launch**
Make sure you are running Python 3.10 or newer: `python --version`.
