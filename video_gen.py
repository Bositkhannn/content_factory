import os
import random
import subprocess
import config


def _format_ass_time(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    hours = cs // 360000
    cs %= 360000
    minutes = cs // 6000
    cs %= 6000
    secs = cs // 100
    cs %= 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _clean_ass_text(text: str) -> str:
    return text.replace("{", "").replace("}", "").replace("\n", " ").strip().upper()


def _build_subtitles(scene_items: list[dict], ass_path: str, hook_banner: str = "") -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,78,&H00FFFFFF,&H0000D7FF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,6,2,2,70,70,480,1
Style: HookTitle,Arial,72,&H0000D7FF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,1,0,1,8,3,8,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]

    banner_text = _clean_ass_text(hook_banner)
    if banner_text and scene_items:
        banner_end = _format_ass_time(max(scene_items[0]["duration"], 1.5))
        lines.append(f"Dialogue: 1,0:00:00.00,{banner_end},HookTitle,,0,0,0,,{banner_text}\n")

    time_offset = 0.0

    for item in scene_items:
        words = item["words"]
        chunk = []
        chunk_chars = 0

        for idx, word in enumerate(words):
            word_text = _clean_ass_text(word["text"])
            if not word_text:
                continue

            chunk.append((word_text, word["start"] + time_offset, word["end"] + time_offset))
            chunk_chars += len(word_text) + 1

            is_last = idx == len(words) - 1
            if len(chunk) >= 3 or chunk_chars >= 18 or is_last:
                start_ts = _format_ass_time(chunk[0][1])
                end_ts = _format_ass_time(max(chunk[-1][2], chunk[0][1] + 0.15))
                phrase = " ".join(c[0] for c in chunk)
                lines.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{phrase}\n")
                chunk = []
                chunk_chars = 0

        time_offset += item["duration"]

    with open(ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _pick_background_music(track_key: str | None = None) -> str | None:
    if not os.path.isdir(config.ASSETS_MUSIC_DIR):
        return None

    valid_ext = (".mp3", ".wav", ".m4a", ".ogg")
    files = [
        f for f in os.listdir(config.ASSETS_MUSIC_DIR)
        if f.lower().endswith(valid_ext)
    ]
    if not files:
        return None

    if track_key:
        target = track_key.lower()
        for f in files:
            stem = os.path.splitext(f)[0].lower()
            if stem == target:
                return os.path.join(config.ASSETS_MUSIC_DIR, f)

    return os.path.join(config.ASSETS_MUSIC_DIR, random.choice(files))


def _resolve_image(output_folder: str, index: int) -> str:
    direct = os.path.join(output_folder, f"scene_{index:02d}.png")
    if os.path.isfile(direct):
        return direct
    available = sorted(
        os.path.join(output_folder, f)
        for f in os.listdir(output_folder)
        if f.endswith(".png")
    )
    if not available:
        raise RuntimeError("Нет сгенерированных изображений для сборки видео")
    return available[min(index - 1, len(available) - 1)]


def _render_scene_clip(
    image_path: str,
    audio_path: str,
    clip_path: str,
    duration: float,
    effect: str,
    is_first: bool,
) -> None:
    fps = min(getattr(config, "VIDEO_FPS", 24), 24)
    threads = str(getattr(config, "FFMPEG_THREADS", 2))
    frames = max(1, int(round(duration * fps))) + 6
    fade_in = "" if is_first else ",fade=t=in:st=0:d=0.18"
    base_scale = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    grade = "vignette=0.95,eq=contrast=1.08:saturation=0.88"

    if effect == "fog_drift":
        filter_complex = (
            f"[0:v]{base_scale},"
            f"zoompan=z='min(zoom+0.001,1.14)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps},"
            f"setpts=PTS-STARTPTS,{grade}{fade_in},format=yuv420p[base];"
            f"color=c=0x808080:s=135x240:d=1:r=1,format=gray,noise=alls=90:allf=u,gblur=sigma=12,"
            f"eq=contrast=2.4:brightness=-0.25,scale=1440:1920:flags=bilinear,"
            f"loop=-1:size=1:start=0,setpts=N/({fps}*TB),"
            f"crop=1080:1920:x='mod(n*1.5,360)':y=0,format=yuv420p[fog];"
            f"[base][fog]blend=all_mode=screen:all_opacity=0.35:shortest=1[v]"
        )
        cmd = [
            config.get_ffmpeg_path(),
            "-y",
            "-threads", threads,
            "-i", image_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            "-shortest",
            clip_path,
        ]
    else:
        if effect == "shake":
            motion = f"zoompan=z='1.12':x='iw/2-(iw/zoom/2)+sin(on*1.9)*14':y='ih/2-(ih/zoom/2)+cos(on*2.5)*14':d={frames}:s=1080x1920:fps={fps}"
            extra = f",{grade}"
        elif effect == "zoom_out":
            motion = f"zoompan=z='max(1.20-0.0014*on,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
            extra = f",{grade}"
        elif effect == "pan_left":
            motion = f"zoompan=z='1.16':x='max(0,(iw-iw/zoom)*(1-on/{frames}))':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
            extra = f",{grade}"
        elif effect == "dark_pulse":
            motion = f"zoompan=z='min(zoom+0.0012,1.16)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
            extra = ",setpts=PTS-STARTPTS,eq=brightness='0.05*sin(6.283*t/1.2)':contrast=1.14:saturation=0.78:eval=frame,vignette=1.05"
        else:
            motion = f"zoompan=z='min(zoom+0.0014,1.20)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
            extra = f",{grade}"

        vf = f"{base_scale},{motion}{extra}{fade_in},format=yuv420p"
        cmd = [
            config.get_ffmpeg_path(),
            "-y",
            "-threads", threads,
            "-i", image_path,
            "-i", audio_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            "-shortest",
            clip_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg clip error ({effect}): {result.stderr[-400:]}")


def build_video(
    output_folder: str,
    scene_items: list[dict],
    music_track: str | None = None,
    hook_banner: str = "",
    on_progress=None,
) -> str:
    abs_folder = os.path.abspath(output_folder)
    threads = str(getattr(config, "FFMPEG_THREADS", 2))
    total = len(scene_items)
    clip_paths = []

    for idx, item in enumerate(scene_items, start=1):
        img_path = _resolve_image(abs_folder, item["index"])
        clip_path = os.path.join(abs_folder, f"_clip_{idx:02d}.mp4")
        effect = item.get("effect", "zoom_in")
        print(f"[VIDEO] Рендер сцены {idx}/{total} (эффект: {effect}, {item['duration']:.2f}с)...")

        _render_scene_clip(
            image_path=img_path,
            audio_path=item["audio_path"],
            clip_path=clip_path,
            duration=item["duration"],
            effect=effect,
            is_first=(idx == 1),
        )
        clip_paths.append(clip_path)

        if on_progress:
            on_progress(idx, total + 1)

    concat_list = os.path.join(abs_folder, "_video_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for path in clip_paths:
            f.write(f"file '{os.path.basename(path)}'\n")

    merged_path = os.path.join(abs_folder, "_merged.mp4")
    merge_res = subprocess.run(
        [
            config.get_ffmpeg_path(),
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "_video_concat.txt",
            "-c", "copy",
            "_merged.mp4",
        ],
        cwd=abs_folder,
        capture_output=True,
        text=True,
        check=False,
    )
    if merge_res.returncode != 0:
        raise RuntimeError(f"FFmpeg concat error: {merge_res.stderr[-400:]}")

    ass_path = os.path.join(abs_folder, "subtitles.ass")
    _build_subtitles(scene_items, ass_path, hook_banner=hook_banner)

    total_duration = sum(item["duration"] for item in scene_items)
    fade_start = max(0.0, total_duration - 2.0)
    music_path = _pick_background_music(music_track)

    print("[VIDEO] Финальная сборка (субтитры + звук)...")
    if music_path:
        print(f"[VIDEO] Фоновая музыка: {os.path.basename(music_path)}")
        filter_complex = (
            f"[0:v]ass=subtitles.ass[v];"
            f"[1:a]volume={config.MUSIC_VOLUME},afade=t=out:st={fade_start:.2f}:d=2.0[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2,dynaudnorm[a]"
        )
        final_cmd = [
            config.get_ffmpeg_path(),
            "-y",
            "-threads", threads,
            "-i", "_merged.mp4",
            "-stream_loop", "-1",
            "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "final.mp4",
        ]
    else:
        print("[VIDEO] Папка assets/music пуста — сборка без фоновой музыки")
        final_cmd = [
            config.get_ffmpeg_path(),
            "-y",
            "-threads", threads,
            "-i", "_merged.mp4",
            "-vf", "ass=subtitles.ass",
            "-af", "dynaudnorm",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "final.mp4",
        ]

    final_res = subprocess.run(
        final_cmd,
        cwd=abs_folder,
        capture_output=True,
        text=True,
        check=False,
    )
    if final_res.returncode != 0:
        raise RuntimeError(f"FFmpeg final error: {final_res.stderr[-400:]}")

    temp_files = clip_paths + [concat_list, merged_path] + [item["audio_path"] for item in scene_items]
    for path in temp_files:
        if os.path.exists(path):
            os.remove(path)

    if on_progress:
        on_progress(total + 1, total + 1)

    return os.path.join(abs_folder, "final.mp4")