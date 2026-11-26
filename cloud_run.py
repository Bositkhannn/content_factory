import json
import os
from datetime import datetime
import requests
import config
from script_gen import generate_script
from audio_gen import generate_scene_audios
from image_gen import generate_images
from video_gen import build_video


def _send_telegram_message(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text[:4000]},
        timeout=30,
    )


def _send_telegram_video(video_path: str, caption: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendVideo"
    with open(video_path, "rb") as video_file:
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "caption": caption[:1024],
                "supports_streaming": "true",
                "width": str(config.IMAGE_WIDTH),
                "height": str(config.IMAGE_HEIGHT),
            },
            files={"video": (os.path.basename(video_path), video_file, "video/mp4")},
            timeout=180,
        )

    if response.status_code != 200:
        raise RuntimeError(f"Telegram API error {response.status_code}: {response.text[:300]}")


def run_cloud_pipeline() -> None:
    topic = os.getenv("TOPIC", "").strip()
    voice_override = os.getenv("VOICE_PROFILE", "auto").strip()

    if not topic:
        raise RuntimeError("Не передана тема ролика (TOPIC)")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(config.OUTPUT_DIR, f"video_{timestamp}")
    os.makedirs(folder, exist_ok=True)

    try:
        script_data = generate_script(topic)
        if voice_override and voice_override != "auto" and voice_override in config.VOICE_PROFILES:
            script_data["voice_profile"] = voice_override

        with open(os.path.join(folder, "script.json"), "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)

        with open(os.path.join(folder, "script.txt"), "w", encoding="utf-8") as f:
            title = script_data.get("title", topic)
            f.write(f"Название: {title}\n\n{script_data['full_text']}\n")

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

        caption = (
            f"{script_data.get('title', topic)}\n\n"
            f"Голос: {script_data.get('voice_profile')}\n"
            f"Трек: {script_data.get('music_track')}\n\n"
            f"{script_data.get('full_text', '')}"
        )
        _send_telegram_video(video_path, caption)
        print("[CLOUD] Видео успешно отправлено в Telegram")
    except Exception as e:
        _send_telegram_message(f"Ошибка генерации по теме «{topic}»:\n{e}")
        raise


if __name__ == "__main__":
    run_cloud_pipeline()