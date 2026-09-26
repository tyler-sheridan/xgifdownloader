#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import tempfile
import random
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def run_command(cmd: list[str], error_message: str) -> None:
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{error_message}\nCommand failed: {' '.join(cmd)}") from exc


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(
            f"Required program '{name}' was not found in PATH. Please install it first."
        )


def download_video(url: str, output_dir: Path) -> Path:
    """
    Download the best available MP4 (or best video+audio merged to MP4 if possible)
    using yt-dlp. Returns the downloaded file path.
    """
    output_template = str(output_dir / "source.%(ext)s")

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "-o",
        output_template,
        # Prefer mp4 when possible.
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        url,
    ]
    run_command(cmd, "Failed to download video from the provided URL.")

    candidates = sorted(output_dir.glob("source.*"))
    video_files = [p for p in candidates if p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}]

    if not video_files:
        raise RuntimeError("Download finished, but no video file was found.")

    # Prefer mp4 if present.
    for file in video_files:
        if file.suffix.lower() == ".mp4":
            return file
    return video_files[0]


def convert_to_gif(
    input_file: Path,
    output_file: Path,
    fps: int,
    width: int,
    start: float | None,
    duration: float | None,
) -> None:
    """
    Convert video to GIF using ffmpeg palettegen/paletteuse for better quality.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        palette_file = Path(tmpdir) / "palette.png"

        # Video filter chain
        vf = f"fps={fps},scale={width}:-1:flags=lanczos"

        palette_cmd = ["ffmpeg", "-y"]
        if start is not None:
            palette_cmd += ["-ss", str(start)]
        palette_cmd += ["-i", str(input_file)]
        if duration is not None:
            palette_cmd += ["-t", str(duration)]
        palette_cmd += [
            "-vf",
            f"{vf},palettegen",
            str(palette_file),
        ]

        run_command(palette_cmd, "Failed to generate GIF palette.")

        gif_cmd = ["ffmpeg", "-y"]
        if start is not None:
            gif_cmd += ["-ss", str(start)]
        gif_cmd += ["-i", str(input_file)]
        if duration is not None:
            gif_cmd += ["-t", str(duration)]
        gif_cmd += [
            "-i",
            str(palette_file),
            "-lavfi",
            f"{vf}[x];[x][1:v]paletteuse",
            str(output_file),
        ]

        run_command(gif_cmd, "Failed to convert video to GIF.")


def build_output_path(user_output: str | None, url: str) -> Path:
    if user_output:
        output = Path(user_output)
        if output.suffix.lower() != ".gif":
            output = output.with_suffix(".gif")
        return output

    random_filename = f"{random.randint(100_000_000_000, 999_999_999_999)}.gif"
    return Path.cwd() / random_filename

def normalize_x_url(url: str) -> str:
    """
    Remove query parameters and fragments from X/Twitter URLs.
    """
    parts = urlsplit(url.strip())

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path.rstrip("/"),
        "",  # remove query string
        "",  # remove fragment
    ))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download an X post video and convert it to a GIF."
    )
    parser.add_argument("url", help="X/Twitter post URL")
    parser.add_argument("-o", "--output", help="Output GIF filename")
    parser.add_argument("--fps", type=int, default=15, help="GIF frames per second (default: 15)")
    parser.add_argument("--width", type=int, default=720, help="Output width in pixels (default: 720)")
    parser.add_argument("--start", type=float, default=None, help="Start time in seconds")
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds")
    args = parser.parse_args()

    try:
        require_binary("ffmpeg")

        output_path = build_output_path(args.output, args.url)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)

            print("Downloading video...")
            video_path = download_video(args.url, temp_dir)
            print(f"Downloaded: {video_path.name}")

            print("Converting to GIF...")
            convert_to_gif(
                input_file=video_path,
                output_file=output_path,
                fps=args.fps,
                width=args.width,
                start=args.start,
                duration=args.duration,
            )

        print(f"Done: {output_path}")

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
