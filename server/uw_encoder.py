#!/usr/bin/env python3

import argparse
import math
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image

# --- Configuration ---
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"
OUTPUT_FPS = 15
AVAILABLE_PATHS = ["circular", "spiral", "sin_h", "sin_v"]
DEFAULT_CROP_DETECT_DURATION = 5
FRAME_FILENAME_PATTERN = "frame_%06d.png"

# --- Helper Function: run_command ---
def run_command(command_list, description, capture_stderr=False):
    print(f"--- Running: {description} ---")
    print(f"Executing: {' '.join(map(str, command_list))}")
    try:
        process = subprocess.run(
            command_list,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        print("Command successful.")
        return process
    except subprocess.CalledProcessError as e:
        print(f"!!! Error executing command: {description} !!!", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        print(f"Command List: {e.cmd}", file=sys.stderr)
        print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        print(f"Stdout:\n{e.stdout}", file=sys.stderr)
        return e
    except FileNotFoundError:
        print(f"!!! Error: Command not found ({command_list[0]}). Is FFmpeg/FFprobe installed and in PATH? !!!", file=sys.stderr)
        return None
    except Exception as e:
        print(f"!!! An unexpected error occurred: {e} !!!", file=sys.stderr)
        return None

def is_animated_gif(path):
    try:
        with Image.open(path) as im:
            return getattr(im, "is_animated", False) and im.n_frames > 1
    except Exception:
        return False

# --- Helper Function: get_video_info ---
def get_video_info(input_path):
    command = [
        FFPROBE_BIN,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,duration,nb_frames",
        "-count_frames",
        "-of", "csv=p=0:s=,",
        str(input_path),
    ]
    print(f"--- Getting video info (including frame count) for: {input_path.name} ---")
    process = run_command(command, f"Get video info ({input_path.name})")

    if process is None or isinstance(process, subprocess.CalledProcessError):
         print(f"!!! Error running ffprobe for {input_path.name} !!!", file=sys.stderr)
         return None, None, None

    output = process.stdout.strip()
    if not output or output.count(',') < 2:
        print(f"!!! Error: Could not parse ffprobe output: '{output}'", file=sys.stderr)
        return None, None, None

    parts = output.split(',')
    if len(parts) < 3:
         print(f"!!! Error: Unexpected ffprobe output format: '{output}'", file=sys.stderr)
         return None, None, None

    try:
        num, den = map(int, parts[0].split('/'))
        fps = float(num) / float(den) if den != 0 else 0
    except (ValueError, ZeroDivisionError):
        print(f"!!! Error: Could not parse frame rate: '{parts[0]}'", file=sys.stderr)
        fps = None

    try:
        duration = float(parts[1])
    except ValueError:
         print(f"!!! Error: Could not parse duration: '{parts[1]}'", file=sys.stderr)
         duration = None

    try:
        if len(parts) >= 3 and parts[2] != 'N/A':
             frame_count = int(parts[2])
        else:
             if duration is not None and fps is not None and fps > 0:
                 print("Warning: Exact frame count not found, estimating from duration and FPS.")
                 frame_count = int(duration * fps)
             else:
                 print("!!! Error: Could not determine frame count.", file=sys.stderr)
                 frame_count = None
    except ValueError:
        print(f"!!! Error: Could not parse frame count: '{parts[2]}'", file=sys.stderr)
        frame_count = None

    if fps is None or duration is None or frame_count is None:
        return None, None, None

    print(f"Detected FPS: {fps:.2f}, Duration: {duration:.2f}s, Frames: {frame_count}")
    return fps, duration, frame_count

# --- Helper Function: detect_crop_area ---
def detect_crop_area(input_path, crop_duration):
    print(f"--- Detecting crop area for: {input_path.name} (duration: {crop_duration}s) ---")
    command = [
        FFMPEG_BIN,
        "-i", str(input_path),
        "-vf", f"cropdetect=limit=24:round=2:reset=0",
        "-t", str(crop_duration),
        "-f", "null",
        "-",
    ]
    process = run_command(command, f"Run cropdetect ({input_path.name})", capture_stderr=True)
    if process is None or isinstance(process, subprocess.CalledProcessError):
        print("!!! Cropdetect command failed. Assuming full frame. !!!", file=sys.stderr)
        return 1920, 1080, 0, 0
    crop_match = re.findall(r"crop=([\d]+):([\d]+):([\d]+):([\d]+)", process.stderr)
    if not crop_match:
        print("!!! Could not parse cropdetect output. Assuming full frame. !!!", file=sys.stderr)
        return 1920, 1080, 0, 0
    cw, ch, cx, cy = map(int, crop_match[-1])
    print(f"Detected crop area: W={cw}, H={ch}, X={cx}, Y={cy}")
    if cw < 100 or ch < 100:
        print(f"!!! Warning: Detected crop area ({cw}x{ch}) seems very small. Reverting to full frame. !!!", file=sys.stderr)
        return 1920, 1080, 0, 0
    return cw, ch, cx, cy

# --- Helper Function: calculate_coords_for_frame ---
def calculate_coords_for_frame(
    frame_number,
    total_frames_in_loop,
    path_type,
    intermediate_size,
    target_width,
    target_height,
    spiral_turns=5,
):
    max_offset_x = intermediate_size - target_width
    max_offset_y = intermediate_size - target_height
    if max_offset_x < 0: max_offset_x = 0
    if max_offset_y < 0: max_offset_y = 0

    radius_x = max_offset_x / 2.0
    radius_y = max_offset_y / 2.0
    center_x = max_offset_x / 2.0
    center_y = max_offset_y / 2.0

    if total_frames_in_loop <= 0: total_frames_in_loop = 1
    t_norm = (frame_number % total_frames_in_loop) / float(total_frames_in_loop)

    x_float, y_float = 0.0, 0.0
    angle = 2 * math.pi * t_norm

    if path_type == "circular":
        x_float = center_x + radius_x * math.cos(angle)
        y_float = center_y + radius_y * math.sin(angle)
    elif path_type == "spiral":
        spiral_progress = abs(1.0 - 2.0 * t_norm)
        current_radius_x = radius_x * spiral_progress
        current_radius_y = radius_y * spiral_progress
        spiral_angle = angle * spiral_turns
        x_float = center_x + current_radius_x * math.cos(spiral_angle)
        y_float = center_y + current_radius_y * math.sin(spiral_angle)
    elif path_type == "sin_h":
        x_float = center_x + radius_x * math.cos(angle)
        y_float = center_y
    elif path_type == "sin_v":
        x_float = center_x
        y_float = center_y + radius_y * math.sin(angle)
    else:
        x_float = center_x
        y_float = center_y

    x_int = max(0, min(int(round(x_float)), max_offset_x))
    y_int = max(0, min(int(round(y_float)), max_offset_y))

    return x_int, y_int

# --- Video Splitting Helper ---
def split_video_if_needed(input_path, max_chunk_seconds=300, min_chunk_seconds=150):
    fps, duration, _ = get_video_info(input_path)
    if duration is None or duration <= max_chunk_seconds:
        return [input_path]

    n_chunks = int(math.ceil(duration / max_chunk_seconds))
    chunk_length = duration / n_chunks
    if chunk_length < min_chunk_seconds and n_chunks > 1:
        n_chunks -= 1
        chunk_length = duration / n_chunks

    chunk_paths = []
    for i in range(n_chunks):
        start = i * chunk_length
        this_chunk = min(chunk_length, duration - start)
        out_path = input_path.parent / f"{input_path.stem}_chunk{i+1}.mp4"
        cmd = [
            FFMPEG_BIN, "-y", "-i", str(input_path),
            "-ss", str(int(start)),
            "-t", str(int(this_chunk)),
            "-c", "copy", str(out_path)
        ]
        result = run_command(cmd, f"Split video chunk {i+1}")
        if result is None or isinstance(result, subprocess.CalledProcessError):
            print(f"Failed to split chunk {i+1} of {input_path.name}", file=sys.stderr)
            continue
        chunk_paths.append(out_path)
    return chunk_paths

def process_static_image(
    input_path,
    output_path,
    target_width,
    target_height,
    output_fps,
    hold_seconds,
    animation_seconds,
    scroll_direction="random",
    overwrite=False,
):
    print(f"\n=== Processing Static Image: {input_path.name} ===")
    if output_path.exists() and not overwrite:
        print(f"Output file {output_path.name} already exists. Skipping.")
        return True

    try:
        img = Image.open(input_path).convert("RGBA")
    except Exception as e:
        print(f"Error loading image {input_path}: {e}", file=sys.stderr)
        return False

    # --- Explicit check for same-size images ---
    if img.width == target_width and img.height == target_height:
        total_frames = int(animation_seconds * output_fps)
        frames = [img.copy()] * total_frames
    else:
        # Preprocess: crop/scale to 96x96 for processing
        intermediate_size = 96
        img = img.copy()
        min_side = min(img.width, img.height)
        left = (img.width - min_side) // 2
        top = (img.height - min_side) // 2
        img = img.crop((left, top, left + min_side, top + min_side))
        img = img.resize((intermediate_size, intermediate_size), Image.LANCZOS)

        total_frames = int(animation_seconds * output_fps)
        hold_frames = int(hold_seconds * output_fps)
        anim_frames = total_frames - 2 * hold_frames
        if anim_frames < 1: anim_frames = 1

        frames = []

        if target_width == target_height:
            max_zoom = min(3.0, intermediate_size / target_width)
            min_zoom = 1.0
            for _ in range(hold_frames):
                frame = img.resize((target_width, target_height), Image.LANCZOS)
                frames.append(frame)
            for i in range(anim_frames):
                t = i / (anim_frames - 1) if anim_frames > 1 else 0
                if t < 0.5:
                    zoom = min_zoom + (max_zoom - min_zoom) * (2 * t)
                else:
                    zoom = max_zoom - (max_zoom - min_zoom) * (2 * (t - 0.5))
                crop_size = int(round(target_width * zoom))
                if crop_size > intermediate_size:
                    crop_size = intermediate_size
                angle = 2 * math.pi * t
                cx = (intermediate_size - crop_size) // 2 + int(
                    (intermediate_size - crop_size) // 2 * math.cos(angle)
                )
                cy = (intermediate_size - crop_size) // 2 + int(
                    (intermediate_size - crop_size) // 2 * math.sin(angle)
                )
                box = (cx, cy, cx + crop_size, cy + crop_size)
                frame = img.crop(box).resize((target_width, target_height), Image.LANCZOS)
                frames.append(frame)
            for _ in range(hold_frames):
                frame = img.resize((target_width, target_height), Image.LANCZOS)
                frames.append(frame)
        else:
            img_scaled = img.resize((target_width, intermediate_size), Image.LANCZOS)
            scroll_dir = scroll_direction
            if scroll_dir == "random":
                scroll_dir = random.choice(["top", "bottom"])
            for _ in range(hold_frames):
                frame = img_scaled.crop((0, 0, target_width, target_height)) \
                    if scroll_dir == "top" \
                    else img_scaled.crop((0, intermediate_size - target_height, target_width, intermediate_size))
                frames.append(frame)
            for i in range(anim_frames):
                t = i / (anim_frames - 1) if anim_frames > 1 else 0
                if t < 0.5:
                    if scroll_dir == "top":
                        y = int((intermediate_size - target_height) * (2 * t))
                    else:
                        y = int((intermediate_size - target_height) * (1 - 2 * t))
                    frame = img_scaled.crop((0, y, target_width, y + target_height))
                else:
                    zoom = 1.0 + (min(3.0, intermediate_size / target_height) - 1.0) * (2 * (t - 0.5))
                    crop_h = int(round(target_height * zoom))
                    crop_h = min(crop_h, intermediate_size)
                    y = (intermediate_size - crop_h) // 2
                    frame = img_scaled.crop((0, y, target_width, y + crop_h)).resize(
                        (target_width, target_height), Image.LANCZOS
                    )
                frames.append(frame)
            for _ in range(hold_frames):
                frame = img_scaled.crop((0, 0, target_width, target_height)) \
                    if scroll_dir == "top" \
                    else img_scaled.crop((0, intermediate_size - target_height, target_width, intermediate_size))
                frames.append(frame)

    # --- Save frames as PNGs and assemble GIF with ffmpeg ---
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        frame_pattern = temp_dir_path / "frame_%06d.png"

        # Save each frame as PNG
        for idx, frame in enumerate(frames):
            frame_path = temp_dir_path / f"frame_{idx+1:06d}.png"
            frame.save(frame_path)

        # Generate palette for better GIF quality
        palette_path = temp_dir_path / "palette.png"
        cmd_palette = [
            FFMPEG_BIN, "-y",
            "-framerate", str(output_fps),
            "-i", str(temp_dir_path / "frame_%06d.png"),
            "-vf", "palettegen",
            str(palette_path),
        ]
        palette_proc = run_command(cmd_palette, "Generate GIF palette from static image frames")
        if palette_proc is None or isinstance(palette_proc, subprocess.CalledProcessError):
            return False

        # Create GIF using palette
        cmd_gif = [
            FFMPEG_BIN, "-y",
            "-framerate", str(output_fps),
            "-i", str(temp_dir_path / "frame_%06d.png"),
            "-i", str(palette_path),
            "-filter_complex", "paletteuse",
            "-loop", "0",
            str(output_path),
        ]
        gif_proc = run_command(cmd_gif, "Create GIF from static image frames")
        if gif_proc is None or isinstance(gif_proc, subprocess.CalledProcessError):
            return False

    print(f"+++ Successfully created GIF: {output_path.name} +++")
    return True

# --- Main Processing Function: process_video (Frame-by-Frame) ---
def process_video(
    input_path,
    output_path,
    intermediate_size,
    target_width,
    target_height,
    loop_duration,
    path_type,
    output_fps,
    spiral_turns,
    overwrite,
    cropdetect_duration,
):
    print(f"\n=== Processing Video (Frame-by-Frame): {input_path.name} ===")
    print(f"    Path Type: {path_type}, Target Size: {target_width}x{target_height}")

    if output_path.exists() and not overwrite:
        print(f"Output file {output_path.name} already exists. Skipping.")
        return True

    base_temp_dir = output_path.parent / f"temp_{input_path.stem}_{os.getpid()}"
    temp_scaled_path = base_temp_dir / f"{input_path.stem}_scaled.mp4"
    temp_frames_dir = base_temp_dir / "raw_frames"
    temp_cropped_frames_dir = base_temp_dir / "cropped_frames"
    temp_palette_path = base_temp_dir / "palette.png"

    if base_temp_dir.exists():
        shutil.rmtree(base_temp_dir)
    base_temp_dir.mkdir(parents=True)
    temp_frames_dir.mkdir()
    temp_cropped_frames_dir.mkdir()

    success = False
    try:
        detected_w, detected_h, detected_x, detected_y = detect_crop_area(input_path, cropdetect_duration)
        if detected_w == 1920 and detected_h == 1080:
            print("Using default 1080x1080 center crop.")
            initial_crop_w, initial_crop_h, initial_crop_x, initial_crop_y = 1080, 1080, 420, 0
        else:
            square_size = min(detected_w, detected_h)
            initial_crop_x = detected_x + (detected_w - square_size) // 2
            initial_crop_y = detected_y + (detected_h - square_size) // 2
            initial_crop_w, initial_crop_h = square_size, square_size
            print(f"Using detected content area to crop: {initial_crop_w}x{initial_crop_h} at ({initial_crop_x},{initial_crop_y})")

        crop_scale_vf = (
            f"crop={initial_crop_w}:{initial_crop_h}:{initial_crop_x}:{initial_crop_y},"
            f"scale={intermediate_size}:{intermediate_size}:flags=lanczos,"
            f"fps={output_fps}"
        )
        cmd_scale = [
            FFMPEG_BIN, "-y", "-i", str(input_path), "-vf", crop_scale_vf,
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            str(temp_scaled_path),
        ]
        scale_process = run_command(cmd_scale, "Crop and Scale Video")
        if scale_process is None or isinstance(scale_process, subprocess.CalledProcessError):
            return False

        scaled_fps, _, total_frames = get_video_info(temp_scaled_path)
        if scaled_fps is None or total_frames is None:
            print("!!! Error getting info from scaled video.", file=sys.stderr)
            return False
        actual_output_fps = scaled_fps if scaled_fps > 0 else output_fps

        cmd_extract = [
            FFMPEG_BIN, "-i", str(temp_scaled_path),
            str(temp_frames_dir / FRAME_FILENAME_PATTERN),
        ]
        extract_process = run_command(cmd_extract, f"Extract {total_frames} Frames")
        if extract_process is None or isinstance(extract_process, subprocess.CalledProcessError):
            return False

        print(f"--- Cropping {total_frames} individual frames ---")
        frames_in_loop = max(1, int(round(loop_duration * actual_output_fps)))
        for n in range(total_frames):
            frame_filename = FRAME_FILENAME_PATTERN % (n + 1)
            input_frame_path = temp_frames_dir / frame_filename
            output_frame_path = temp_cropped_frames_dir / frame_filename

            if not input_frame_path.exists():
                 print(f"Warning: Expected frame {input_frame_path} not found, skipping.", file=sys.stderr)
                 continue

            x, y = calculate_coords_for_frame(
                n, frames_in_loop, path_type, intermediate_size,
                target_width, target_height, spiral_turns
            )

            crop_box = (x, y, x + target_width, y + target_height)

            try:
                with Image.open(input_frame_path) as img:
                    cropped_img = img.crop(crop_box)
                    cropped_img.save(output_frame_path)
            except Exception as e:
                print(f"!!! Error cropping frame {n+1}: {e}", file=sys.stderr)
                return False

            if (n + 1) % 100 == 0 or (n + 1) == total_frames:
                print(f"    Cropped frame {n + 1}/{total_frames}")

        cmd_palette = [
            FFMPEG_BIN, "-y",
            "-i", str(temp_cropped_frames_dir / FRAME_FILENAME_PATTERN),
            "-vf", "palettegen",
            str(temp_palette_path),
        ]
        palette_process = run_command(cmd_palette, "Generate Palette from Cropped Frames")
        if palette_process is None or isinstance(palette_process, subprocess.CalledProcessError):
            return False

        cmd_gif = [
            FFMPEG_BIN, "-y",
            "-framerate", str(actual_output_fps),
            "-i", str(temp_cropped_frames_dir / FRAME_FILENAME_PATTERN),
            "-i", str(temp_palette_path),
            "-filter_complex", "paletteuse",
            "-loop", "0",
            str(output_path),
        ]
        gif_process = run_command(cmd_gif, "Create Final GIF")
        if gif_process is None or isinstance(gif_process, subprocess.CalledProcessError):
            return False

        print(f"+++ Successfully created GIF: {output_path.name} +++")
        success = True
        return True

    finally:
        print("--- Cleaning up temporary files ---")
        if base_temp_dir.exists():
            try:
                shutil.rmtree(base_temp_dir)
                print(f"Removed temp directory {base_temp_dir}")
            except OSError as e:
                print(f"Warning: Could not remove temp directory {base_temp_dir}: {e}", file=sys.stderr)

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(
        description="Process video clips and images recursively for LED panels.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input_folder", type=str, help="Path to the root folder containing MP4 clips or images (searches recursively)."
    )
    parser.add_argument(
        "output_folder", type=str, help="Path to the folder to save output GIFs."
    )
    parser.add_argument(
        "--target-width", type=int, default=32, help="Width (pixels) of the target LED panel/output GIF."
    )
    parser.add_argument(
        "--target-height", type=int, default=32, help="Height (pixels) of the target LED panel/output GIF."
    )
    parser.add_argument(
        "--intermediate-size", type=int, default=200, help="Size (pixels) to scale the central square crop to before sampling. Must be >= target width/height."
    )
    parser.add_argument(
        "--loop-duration", type=float, default=30.0, help="Duration (seconds) for one full path loop."
    )
    parser.add_argument(
        "--path-type", type=str, default="random", choices=AVAILABLE_PATHS + ["random"], help="Type of path for the sample window. 'random' selects one per video."
    )
    parser.add_argument(
        "--spiral-turns", type=int, default=5, help="Number of turns for the spiral path (relevant only if path-type is spiral)."
    )
    parser.add_argument(
        "--output-fps", type=int, default=OUTPUT_FPS, help="Target frame rate for the output animated GIF (actual rate might depend on source)."
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing output files."
    )
    parser.add_argument(
        "--cropdetect-duration", type=int, default=DEFAULT_CROP_DETECT_DURATION, help="Seconds of video to analyze for black bar detection."
    )
    parser.add_argument(
        "--image-hold-seconds", type=float, default=5.0,
        help="Seconds to hold at start/end of static image animation."
    )
    parser.add_argument(
        "--image-animation-seconds", type=float, default=120.0,
        help="Total duration (seconds) of animated GIF from static image."
    )
    parser.add_argument(
        "--image-scroll-direction", type=str, default="random",
        choices=["top", "bottom", "random"],
        help="For non-square outputs, scroll from top or bottom (or random)."
    )

    args = parser.parse_args()

    if args.intermediate_size < args.target_width or args.intermediate_size < args.target_height:
         print(f"Error: --intermediate-size ({args.intermediate_size}) must be >= target width/height.", file=sys.stderr)
         sys.exit(1)

    input_dir = Path(args.input_folder)
    output_dir = Path(args.output_folder)

    if not input_dir.is_dir():
        print(f"Error: Input folder not found or not a directory: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Input folder (recursive): {input_dir.resolve()}")
    print(f"Output folder: {output_dir.resolve()}")
    print(f"Target Size: {args.target_width}x{args.target_height}")
    print(f"Intermediate Size: {args.intermediate_size}x{args.intermediate_size}")
    print(f"Loop Duration: {args.loop_duration}s")
    print(f"Path Type Mode: {args.path_type}")
    if args.path_type == "spiral": print(f"Spiral Turns: {args.spiral_turns}")
    print(f"Target Output GIF FPS: {args.output_fps}")
    print(f"Crop Detect Duration: {args.cropdetect_duration}s")
    print(f"Overwrite existing: {args.overwrite}")
    print(f"Image Hold Seconds: {args.image_hold_seconds}")
    print(f"Image Animation Seconds: {args.image_animation_seconds}")
    print(f"Image Scroll Direction: {args.image_scroll_direction}")

    print("--- Checking for FFmpeg and FFprobe ---")
    check_ffmpeg = run_command([FFMPEG_BIN, "-version"], "Check FFmpeg")
    if check_ffmpeg is None or isinstance(check_ffmpeg, subprocess.CalledProcessError): sys.exit(1)
    check_ffprobe = run_command([FFPROBE_BIN, "-version"], "Check FFprobe")
    if check_ffprobe is None or isinstance(check_ffprobe, subprocess.CalledProcessError): sys.exit(1)

    processed_count = 0
    skipped_count = 0
    error_count = 0

    print(f"\n--- Searching for media files recursively in {input_dir} ---")
    video_files = list(input_dir.rglob("*.mp4")) + list(input_dir.rglob("*.MP4"))
    image_files = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.PNG", "*.JPG", "*.JPEG", "*.WEBP", "*.GIF"):
        image_files.extend(input_dir.rglob(ext))

    if not video_files and not image_files:
        print("No MP4 or image files found recursively in the input folder.")
        sys.exit(0)

    print(f"\nFound {len(video_files)} MP4 files and {len(image_files)} image files to process...")

    # --- Video processing loop ---
    for video_path in video_files:
        video_chunks = split_video_if_needed(video_path)
        for chunk_path in video_chunks:
            current_path_type = args.path_type
            if current_path_type == "random":
                current_path_type = random.choice(AVAILABLE_PATHS)
            output_gif_path = output_dir / f"{chunk_path.stem}_{current_path_type}_{args.target_width}x{args.target_height}.gif"
            try:
                relative_path = chunk_path.relative_to(input_dir)
                print(f"\nProcessing input file: {relative_path}")
            except ValueError:
                print(f"\nProcessing input file: {chunk_path}")

            try:
                result = process_video(
                    input_path=chunk_path,
                    output_path=output_gif_path,
                    intermediate_size=args.intermediate_size,
                    target_width=args.target_width,
                    target_height=args.target_height,
                    loop_duration=args.loop_duration,
                    path_type=current_path_type,
                    output_fps=args.output_fps,
                    spiral_turns=args.spiral_turns,
                    overwrite=args.overwrite,
                    cropdetect_duration=args.cropdetect_duration,
                )
                if result is True:
                    if output_gif_path.exists():
                        processed_count += 1
                    else:
                        skipped_count += 1
                elif result is False:
                     error_count += 1

            except ImportError:
                 print("!!! ERROR: Pillow library not found. Please install it: pip install Pillow !!!", file=sys.stderr)
                 sys.exit(1)
            except Exception as e:
                print(f"!!! UNHANDLED EXCEPTION processing {chunk_path.name}: {e} !!!", file=sys.stderr)
                import traceback
                traceback.print_exc()
                error_count += 1
                base_temp_dir = output_dir / f"temp_{chunk_path.stem}_{os.getpid()}"
                if base_temp_dir.exists():
                     try:
                         print(f"Attempting cleanup of {base_temp_dir} after error...")
                         shutil.rmtree(base_temp_dir)
                     except OSError as cleanup_e:
                         print(f"Warning: Could not remove temp directory {base_temp_dir} after error: {cleanup_e}", file=sys.stderr)

    # --- Image processing loop ---
    for image_path in image_files:
        output_gif_path = output_dir / f"{image_path.stem}_{args.target_width}x{args.target_height}.gif"
        try:
            if image_path.suffix.lower() == ".gif":
                if is_animated_gif(image_path):
                    # Treat as video
                    current_path_type = args.path_type
                    if current_path_type == "random":
                        current_path_type = random.choice(AVAILABLE_PATHS)
                    result = process_video(
                        input_path=image_path,
                        output_path=output_gif_path,
                        intermediate_size=args.intermediate_size,
                        target_width=args.target_width,
                        target_height=args.target_height,
                        loop_duration=args.loop_duration,
                        path_type=current_path_type,
                        output_fps=args.output_fps,
                        spiral_turns=args.spiral_turns,
                        overwrite=args.overwrite,
                        cropdetect_duration=args.cropdetect_duration,
                    )
                else:
                    # Treat as static image
                    result = process_static_image(
                        input_path=image_path,
                        output_path=output_gif_path,
                        target_width=args.target_width,
                        target_height=args.target_height,
                        output_fps=args.output_fps,
                        hold_seconds=args.image_hold_seconds,
                        animation_seconds=args.image_animation_seconds,
                        scroll_direction=args.image_scroll_direction,
                        overwrite=args.overwrite,
                    )
            else:
                # Not a GIF, treat as static image
                result = process_static_image(
                    input_path=image_path,
                    output_path=output_gif_path,
                    target_width=args.target_width,
                    target_height=args.target_height,
                    output_fps=args.output_fps,
                    hold_seconds=args.image_hold_seconds,
                    animation_seconds=args.image_animation_seconds,
                    scroll_direction=args.image_scroll_direction,
                    overwrite=args.overwrite,
                )
            if result is True:
                processed_count += 1
            elif result is False:
                error_count += 1
        except ImportError:
            print("!!! ERROR: Pillow library not found. Please install it: pip install Pillow !!!", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"!!! UNHANDLED EXCEPTION processing {image_path.name}: {e} !!!", file=sys.stderr)
            import traceback
            traceback.print_exc()
            error_count += 1

    print("\n=== Processing Summary ===")
    print(f"Successfully processed/overwritten: {processed_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    main()

