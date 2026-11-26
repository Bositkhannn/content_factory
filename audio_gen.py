import array
import asyncio
import gc
import os
import re
import subprocess
import wave
import edge_tts
import requests
import config

_silero_model = None


def _clean_tts_text(text: str) -> str:
    cleaned = text.replace("—", ", ").replace("–", ", ")
    cleaned = cleaned.replace("«", "").replace("»", "").replace('"', "")
    cleaned = re.sub(r"[*_#`~<>[\]{}|\\]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _get_audio_duration(file_path: str) -> float:
    cmd = [
        config.get_ffprobe_path(),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def _distribute_words(text: str, start_time: float, end_time: float) -> list[dict]:
    tokens = text.split()
    if not tokens:
        return []

    weights = []
    for token in tokens:
        base = max(len(re.sub(r"[^\w]", "", token)), 2)
        if token.endswith((".", "!", "?")):
            base += 5
        elif token.endswith((",", ":", ";")):
            base += 2.5
        weights.append(base)

    total_weight = sum(weights)
    span = max(end_time - start_time, 0.1)
    cursor = start_time
    result = []

    for token, weight in zip(tokens, weights):
        part = span * (weight / total_weight)
        result.append({
            "text": token,
            "start": cursor,
            "end": cursor + part,
        })
        cursor += part

    return result


def _load_silero_model():
    global _silero_model
    if _silero_model is not None:
        return _silero_model

    import torch

    torch.set_num_threads(2)
    os.makedirs(config.ASSETS_MODELS_DIR, exist_ok=True)

    if not os.path.isfile(config.SILERO_MODEL_PATH):
        print("[TTS] Первая загрузка модели Silero (~60 МБ)...")
        response = requests.get(config.SILERO_MODEL_URL, timeout=120)
        response.raise_for_status()
        with open(config.SILERO_MODEL_PATH, "wb") as f:
            f.write(response.content)

    importer = torch.package.PackageImporter(config.SILERO_MODEL_PATH)
    model = importer.load_pickle("tts_models", "model")
    model.to(torch.device("cpu"))
    _silero_model = model
    return _silero_model


def _unload_silero_model() -> None:
    global _silero_model
    if _silero_model is not None:
        _silero_model = None
        gc.collect()


def _apply_audio_filter(input_path: str, output_path: str, af_filter: str) -> None:
    cmd = [
        config.get_ffmpeg_path(),
        "-y",
        "-i", input_path,
        "-af", af_filter,
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio filter error: {res.stderr[-300:]}")


def _synthesize_silero(text: str, output_path: str, speaker: str, af_filter: str) -> None:
    clean_text = _clean_tts_text(text)
    if re.search(r"[0-9A-Za-z]", clean_text):
        raise ValueError("Текст содержит цифры или латиницу")

    import torch

    model = _load_silero_model()
    sample_rate = 48000
    audio_tensor = model.apply_tts(
        text=clean_text,
        speaker=speaker,
        sample_rate=sample_rate,
    )
    pcm_values = (audio_tensor.clamp(-1.0, 1.0) * 32767.0).to(torch.int16).tolist()
    raw_wav = output_path + ".raw.wav"

    try:
        with wave.open(raw_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(array.array("h", pcm_values).tobytes())

        _apply_audio_filter(raw_wav, output_path, af_filter)
    finally:
        if os.path.exists(raw_wav):
            os.remove(raw_wav)


async def _synthesize_edge(text: str, output_path: str, voice: str, af_filter: str) -> None:
    clean_text = _clean_tts_text(text)
    raw_mp3 = output_path + ".raw.mp3"
    last_error = None

    for attempt in range(1, 4):
        try:
            communicate = edge_tts.Communicate(text=clean_text, voice=voice)
            audio_buffer = bytearray()

            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    audio_buffer.extend(chunk["data"])

            if not audio_buffer:
                raise RuntimeError("Получен пустой аудиопоток")

            with open(raw_mp3, "wb") as audio_file:
                audio_file.write(audio_buffer)

            _apply_audio_filter(raw_mp3, output_path, af_filter)
            return
        except Exception as e:
            last_error = e
            print(f"[TTS] Edge попытка {attempt} не удалась: {e}")
            await asyncio.sleep(1.5)
        finally:
            if os.path.exists(raw_mp3):
                os.remove(raw_mp3)

    raise RuntimeError(f"Не удалось озвучить через Edge: {last_error}")


def _merge_scene_audios(audio_paths: list[str], output_path: str) -> None:
    folder = os.path.dirname(os.path.abspath(output_path))
    list_file = os.path.join(folder, "_audio_concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for path in audio_paths:
            name = os.path.basename(path)
            f.write(f"file '{name}'\n")

    try:
        subprocess.run(
            [
                config.get_ffmpeg_path(),
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", "_audio_concat.txt",
                "-c", "copy",
                os.path.basename(output_path),
            ],
            cwd=folder,
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


async def _generate_all(
    scenes: list[dict],
    output_folder: str,
    voice_profile: str,
    on_progress=None,
) -> list[dict]:
    profile = config.VOICE_PROFILES.get(voice_profile) or config.VOICE_PROFILES[config.DEFAULT_VOICE_PROFILE]
    engine = profile["engine"]
    speaker = profile["speaker"]
    af_filter = profile.get("af", "aresample=44100")

    results = []
    total = len(scenes)
    print(f"[TTS] Выбран профиль: {voice_profile} ({engine}:{speaker})")

    try:
        for index, scene in enumerate(scenes, start=1):
            audio_path = os.path.join(output_folder, f"scene_{index:02d}.mp3")
            print(f"[TTS] Озвучка сцены {index}/{total}: {scene['text'][:55]}...")

            if engine == "silero":
                try:
                    _synthesize_silero(scene["text"], audio_path, speaker, af_filter)
                except Exception as e:
                    print(f"[TTS] Silero пропущен ({e}), откат на Edge...")
                    await _synthesize_edge(
                        scene["text"],
                        audio_path,
                        "ru-RU-SvetlanaNeural",
                        "aresample=44100",
                    )
            else:
                await _synthesize_edge(scene["text"], audio_path, speaker, af_filter)

            duration = _get_audio_duration(audio_path)
            words = _distribute_words(scene["text"], 0.0, duration)

            results.append({
                "index": index,
                "text": scene["text"],
                "effect": scene.get("effect", "zoom_in"),
                "audio_path": audio_path,
                "duration": duration,
                "words": words,
            })

            if on_progress:
                on_progress(index, total)

            if engine == "edge" and index < total:
                await asyncio.sleep(0.5)
    finally:
        _unload_silero_model()

    return results


def generate_scene_audios(
    scenes: list[dict],
    output_folder: str,
    voice_profile: str | None = None,
    on_progress=None,
) -> list[dict]:
    selected = voice_profile or config.DEFAULT_VOICE_PROFILE
    scene_audios = asyncio.run(
        _generate_all(scenes, output_folder, selected, on_progress=on_progress)
    )
    audio_paths = [item["audio_path"] for item in scene_audios]
    combined_path = os.path.join(output_folder, "voice.mp3")
    _merge_scene_audios(audio_paths, combined_path)
    return scene_audios