import html
import json
import os
import time
from datetime import datetime
import requests
import config
from script_gen import generate_script
from audio_gen import generate_scene_audios
from image_gen import generate_images
from video_gen import build_video

TELEGRAM_MAX_MB = 49.0


def _get_telegram_creds() -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return token, chat_id


def _telegram_request(method: str, data: dict, files: dict | None = None, timeout: int = 60) -> None:
    token, _ = _get_telegram_creds()
    url = f"https://api.telegram.org/bot{token}/{method}"
    last_error = None

    for attempt in range(1, 4):
        try:
            if files:
                file_path = files["video_path"]
                with open(file_path, "rb") as video_file:
                    response = requests.post(
                        url,
                        data=data,
                        files={"video": (os.path.basename(file_path), video_file, "video/mp4")},
                        timeout=timeout,
                    )
            else:
                response = requests.post(url, data=data, timeout=timeout)

            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as e:
            last_error = str(e)

        print(f"[CLOUD] Telegram {method} попытка {attempt} не удалась: {last_error}")
        if attempt < 3:
            time.sleep(2.5 * attempt)

    raise RuntimeError(f"Telegram API error ({method}): {last_error}")


def _send_telegram_message(text: str, parse_mode: str | None = None) -> None:
    token, chat_id = _get_telegram_creds()
    if not token or not chat_id:
        return
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    _telegram_request("sendMessage", payload, timeout=30)


def _send_telegram_video(video_path: str, caption: str) -> None:
    token, chat_id = _get_telegram_creds()
    if not token or not chat_id:
        raise RuntimeError("Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if size_mb > TELEGRAM_MAX_MB:
        raise RuntimeError(
            f"Файл видео слишком большой для Telegram Bot API ({size_mb:.1f} МБ > {TELEGRAM_MAX_MB} МБ). "
            "Скачай final.mp4 из Artifacts в GitHub Actions."
        )

    payload = {
        "chat_id": chat_id,
        "caption": caption[:1024],
        "supports_streaming": "true",
        "width": str(getattr(config, "IMAGE_WIDTH", 1080)),
        "height": str(getattr(config, "IMAGE_HEIGHT", 1920)),
    }
    _telegram_request("sendVideo", payload, files={"video_path": video_path}, timeout=180)


def _format_publish_package(title: str, description: str, hashtags: str, pinned_comment: str) -> str:
    safe_title = html.escape(title)
    desc_block = f"{description}\n\n{hashtags}".strip() if description else hashtags
    safe_desc = html.escape(desc_block)

    parts = [
        f"<b>Название (тапни чтобы скопировать):</b>\n<code>{safe_title}</code>",
        f"<b>Описание и хештеги:</b>\n<code>{safe_desc}</code>",
    ]
    if pinned_comment:
        parts.append(f"<b>Закреплённый комментарий:</b>\n<code>{html.escape(pinned_comment)}</code>")

    return "\n\n".join(parts)


def run_cloud_pipeline() -> None:
    started_at = time.monotonic()
    topic = os.getenv("TOPIC", "").strip()
    voice_override = os.getenv("VOICE_PROFILE", "auto").strip()
    music_override = os.getenv("MUSIC_TRACK", "auto").strip()
    channel = os.getenv("CHANNEL", "default").strip()
    if not channel or channel == "default":
        channel = None

    if not topic:
        raise RuntimeError("Не передана тема ролика (TOPIC)")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(config.OUTPUT_DIR, f"video_{timestamp}")
    os.makedirs(folder, exist_ok=True)

    try:
        script_data = generate_script(topic, channel=channel)

        voices = getattr(config, "VOICE_PROFILES", {})
        if voice_override and voice_override != "auto" and voice_override in voices:
            script_data["voice_profile"] = voice_override

        tracks = getattr(config, "MUSIC_TRACKS", {})
        if music_override and music_override != "auto" and music_override in tracks:
            script_data["music_track"] = music_override

        yt_title = script_data.get("title", topic)
        yt_desc = script_data.get("youtube_description", "")
        yt_tags = script_data.get("hashtags_str", "#shorts")
        yt_comment = script_data.get("pinned_comment", "")

        with open(os.path.join(folder, "script.json"), "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)

        with open(os.path.join(folder, "script.txt"), "w", encoding="utf-8") as f:
            f.write(f"Название: {yt_title}\n\n{script_data['full_text']}\n")

        with open(os.path.join(folder, "youtube_post.txt"), "w", encoding="utf-8") as f:
            f.write(f"{yt_title}\n\n{yt_desc}\n\n{yt_tags}\n")
            if yt_comment:
                f.write(f"\nЗакреплённый комментарий:\n{yt_comment}\n")

        scene_audios = generate_scene_audios(
            script_data["scenes"],
            folder,
            voice_profile=script_data.get("voice_profile"),
        )

        generate_images(script_data["image_prompts"], folder)

        video_path = build_video(
            folder,
            scene_audios,
            music_track=script_data.get("music_track"),
            hook_banner=script_data.get("hook_banner", ""),
        )

        total_duration = sum(item.get("duration", 0.0) for item in scene_audios)
        elapsed_sec = int(time.monotonic() - started_at)
        minutes, seconds = divmod(elapsed_sec, 60)

        warning_line = ""
        if total_duration > 59.0:
            warning_line = f"\nВнимание: длина {total_duration:.1f}с (>59с, может не попасть в Shorts)"

        caption = (
            f"{yt_title}\n\n"
            f"Канал: {script_data.get('channel', 'dark_psychology')}\n"
            f"Голос: {script_data.get('voice_profile')}\n"
            f"Трек: {script_data.get('music_track')}\n"
            f"Длительность: {total_duration:.1f}с | Сборка: {minutes}м {seconds:02d}с"
            f"{warning_line}"
        )
        _send_telegram_video(video_path, caption)

        publish_text = _format_publish_package(yt_title, yt_desc, yt_tags, yt_comment)
        _send_telegram_message(publish_text, parse_mode="HTML")
        print("[CLOUD] Видео и SEO-пакет успешно отправлены в Telegram")
    except Exception as e:
        _send_telegram_message(f"Ошибка генерации по теме «{topic}»:\n{e}")
        raise


if __name__ == "__main__":
    run_cloud_pipeline()
