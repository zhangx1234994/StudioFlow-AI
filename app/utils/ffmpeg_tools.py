from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def make_image_clip(image_path: Path, output_path: Path, duration_sec: int) -> bool:
    if not has_ffmpeg():
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-t",
        str(duration_sec),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-r",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def concat_videos(video_paths: list[Path], output_path: Path) -> bool:
    if not has_ffmpeg() or not video_paths:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = output_path.parent / f"{output_path.stem}_concat.txt"
    lines = [f"file '{path.as_posix()}'" for path in video_paths]
    list_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
