# ffmpeg_utils.py
# Handles locating ffmpeg on the system and running conversions.
# Nothing in here should touch tkinter — keep UI and process logic separate.

import shutil
import subprocess
from pathlib import Path


WINGET_PATH = (
    r"C:\Users\gumba\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
)

# CRF values mapped to the quality labels shown in the dropdown.
CRF_MAP = {
    "0":  "Lossless (CRF 0)",
    "18": "High (CRF 18)",
    "23": "Medium (CRF 23)",
    "28": "Low (CRF 28)",
}


def find_ffmpeg() -> str | None:
    """Return the path to ffmpeg.exe, or None if it cannot be found.

    Search order:
      1. Same directory as this script (portable drop-in)
      2. System PATH
      3. Known WinGet install location for Gyan's ffmpeg build
    """
    local = Path(__file__).parent / "ffmpeg.exe"
    if local.exists():
        return str(local)

    found = shutil.which("ffmpeg")
    if found:
        return found

    winget = Path(WINGET_PATH)
    if winget.exists():
        return str(winget)

    return None


def label_to_crf(quality_label: str) -> str:
    """Map a quality dropdown label back to its CRF integer string."""
    for crf, label in CRF_MAP.items():
        if crf in quality_label:
            return crf
    return "23"


def run_conversion(ffmpeg_path: str, input_path: str, output_path: str, crf: str) -> tuple[bool, str]:
    """Run a single ffmpeg conversion and return (success, error_message).

    Video is encoded with H.264 (libx264). Audio is re-encoded to AAC at
    192 kbps. yuv420p is forced so files with exotic pixel formats convert
    cleanly — some AVI containers use formats libx264 refuses without it.

    Returns:
        (True, "")            on success
        (False, error_msg)    on failure, where error_msg is the last
                              meaningful line from ffmpeg's stderr output
    """
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-crf", crf,
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore").strip().splitlines()
            error_msg = next(
                (line for line in reversed(stderr) if line.strip() and not line.startswith("  ")),
                "Unknown FFmpeg error",
            )
            return False, error_msg

        return True, ""

    except Exception as exc:
        return False, str(exc)
