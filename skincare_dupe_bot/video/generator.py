"""Assembles a scene list + script into a finished vertical reel via gTTS + ffmpeg."""
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from gtts import gTTS

from skincare_dupe_bot import config
from skincare_dupe_bot.database.db import get_session
from skincare_dupe_bot.database.models import GeneratedVideo
from skincare_dupe_bot.video.image_builder import build_scene_images
from skincare_dupe_bot.video.script_writer import generate_script


def _audio_duration_seconds(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _build_silent_video(scene_paths, durations, out_path: Path):
    concat_list = out_path.parent / "concat_list.txt"
    with open(concat_list, "w") as f:
        for path, duration in zip(scene_paths, durations):
            f.write(f"file '{path}'\nduration {duration}\n")
        # ffmpeg concat demuxer needs the last file repeated without a duration
        f.write(f"file '{scene_paths[-1]}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-vf", f"fps={config.VIDEO_FPS},format=yuv420p",
            str(out_path),
        ],
        capture_output=True, check=True,
    )


def _mux_audio_video(video_path: Path, audio_path: Path, out_path: Path):
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
            str(out_path),
        ],
        capture_output=True, check=True,
    )


def generate_reel(kbeauty, dupe, trigger_reason="scheduled_rotation") -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="skincare_reel_"))
    try:
        script = generate_script(kbeauty, dupe)

        images = build_scene_images(kbeauty, dupe, script)
        scene_paths = []
        for i, img in enumerate(images):
            p = tmp_dir / f"scene_{i}.png"
            img.save(p)
            scene_paths.append(p)

        audio_path = tmp_dir / "voiceover.mp3"
        gTTS(text=script.full_narration, lang="en").save(str(audio_path))
        audio_duration = _audio_duration_seconds(audio_path)

        base_duration = config.SECONDS_PER_SCENE * len(scene_paths)
        if audio_duration > base_duration:
            per_scene = audio_duration / len(scene_paths)
            durations = [per_scene] * len(scene_paths)
        else:
            durations = [config.SECONDS_PER_SCENE] * len(scene_paths)

        silent_video_path = tmp_dir / "silent.mp4"
        _build_silent_video(scene_paths, durations, silent_video_path)

        config.VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        config.READY_TO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        video_id = uuid.uuid4().hex[:10]
        final_video_path = config.VIDEO_OUTPUT_DIR / f"{dupe.brand}_{dupe.id}_{video_id}.mp4".replace(" ", "_")
        _mux_audio_video(silent_video_path, audio_path, final_video_path)

        ready_video_path = config.READY_TO_UPLOAD_DIR / final_video_path.name
        shutil.copy(final_video_path, ready_video_path)

        caption_path = ready_video_path.with_suffix(".txt")
        caption_path.write_text(f"{script.caption}\n\n{script.hashtags}\n")

        with get_session() as session:
            session.add(
                GeneratedVideo(
                    dupe_id=dupe.id,
                    file_path=str(final_video_path),
                    caption=script.caption,
                    hashtags=script.hashtags,
                    trigger_reason=trigger_reason,
                )
            )

        return final_video_path
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
