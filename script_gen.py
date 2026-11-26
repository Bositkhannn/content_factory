import json
import re
import time
import requests
from google import genai
from google.genai import types
import config

ALLOWED_EFFECTS = {
    "zoom_in",
    "zoom_out",
    "shake",
    "fog_drift",
    "dark_pulse",
    "pan_left",
}

DEFAULT_CHANNEL_PRESET = {
    "name": "dark_psychology",
    "style": "тёмная психология, холодный, уверенный, без воды",
    "authority_examples": (
        '"Существует четыре научно доказанных способа.", '
        '"Поведенческая психология выделяет три проверенных приёма.", '
        '"Есть четыре подтверждённых экспериментами правила."'
    ),
    "cta_examples": (
        '"Хочешь узнать больше о том, как раскусить манипулятора и не стать его пешкой? '
        'Тогда подпишись на канал, чтобы не пропустить новые видео — здесь мы вскрываем всё о тёмной психологии."\n'
        '         "Остальные так и будут попадаться на этот трюк. '
        'Подпишись прямо сейчас, если хочешь видеть скрытые мотивы людей и не пропустить следующие разборы."'
    ),
    "visual_style": "dark cinematic lighting, moody shadows, hyperrealistic, 8k, no text",
    "required_hashtags": ["#shorts", "#темнаяпсихология"],
    "default_voice": "dark_male",
}


def _get_channel_preset(channel: str | None) -> dict:
    preset = dict(DEFAULT_CHANNEL_PRESET)
    presets = getattr(config, "CHANNEL_PRESETS", None)
    if channel and isinstance(presets, dict) and channel in presets:
        preset.update(presets[channel])
    return preset


def _build_prompt(topic: str, preset: dict) -> str:
    tracks = getattr(config, "MUSIC_TRACKS", {})
    tracks_block = "\n".join(
        f'    - "{key}" ({desc})'
        for key, desc in tracks.items()
    )

    voices = getattr(config, "VOICE_PROFILES", {})
    voices_block = "\n".join(
        f'    - "{key}" ({item.get("description", key)})'
        for key, item in voices.items()
    )

    required_tags = ", ".join(preset["required_hashtags"])
    default_voice = preset.get("default_voice", getattr(config, "DEFAULT_VOICE_PROFILE", "dark_male"))
    default_track = next(iter(tracks), "manipulation")

    return f"""
    Создай сценарий, раскадровку и SEO-метаданные для короткого вертикального видео YouTube Shorts на тему: "{topic}".
    Стиль: {preset["style"]}. Текст должен звучать как живая речь умного и уверенного рассказчика, а не как сгенерированная нейросетью статья.
    Общая длительность речи — строго 35–52 секунды (не длиннее 55 секунд).

    СТРОГАЯ СТРУКТУРА СЦЕН:
    1. Сцена 1 — ОГЛАВЛЕНИЕ-ХУК + НАУЧНЫЙ ЯКОРЬ (2–4 секунды речи):
       - Начни строго с прямого и чёткого обозначения темы ролика (например: "Как защитить себя от манипулятора?").
       - Сразу после вопроса/темы дай короткую подводку с опорой на авторитет (варьируй формулировки, например: {preset["authority_examples"]}).
       - Если в теме уже указано число (например, "3 фразы" или "5 причин"), используй ровно это число пунктов. Если числа в теме нет — сделай 3 или 4 пункта.
    2. Следующие сцены — ПО ОДНОЙ СЦЕНЕ НА КАЖДЫЙ ПУНКТ:
       - Каждый пункт начинай чётко со слова-маркера: "Первый.", "Второй.", "Третий.", "Четвёртый." (или "Первое.", "Второе." — согласуй по роду).
       - В каждом пункте 1–2 коротких, острых, конкретных предложения. Без общих слов.
    3. Последняя сцена — ДОМИНАНТНЫЙ ПРИЗЫВ К ПОДПИСКЕ (CTA):
       - НЕ проси и НЕ умоляй подписаться. Запрещены фразы вроде "пожалуйста", "поддержите канал", "ставьте лайк".
       - Построй финал как вызов, укол в самолюбие или рациональный выбор строго под тему этого ролика.
       - Примеры нужной интонации (обязательно адаптируй под текущую тему "{topic}"):
         {preset["cta_examples"]}
       - Никаких упоминаний Telegram, ссылок в описании или лайков — только подписка на канал.

    ЗАПРЕЩЕНО:
    - Канцелярит и ИИ-штампы ("в современном мире", "данный способ", "важно понимать", "является", "не секрет что", "многие люди сталкиваются").
    - Цифры, знак процента и латиница внутри поля "text" диктора: все числа пиши строго русскими словами ("четыре", "тридцать", "двадцать процентов").
    - Пометки диктору, скобки, эмодзи, хештеги внутри поля "text".

    Выбери один самый подходящий фоновый трек строго из списка:
{tracks_block}

    Выбери один самый подходящий голос диктора строго из списка:
{voices_block}

    Для каждой сцены выбери один спецэффект строго из списка:
    - "shake" (резкая тряска — для оглавления-хука, угроз, резких фактов)
    - "fog_drift" (плывущий туман — для скрытых мотивов, тайн, одиночества)
    - "dark_pulse" (пульсация света и зерно — для давления, тревоги, финала)
    - "zoom_in" (наезд камеры — для акцента на пункте)
    - "zoom_out" (отъезд камеры — для развязки)
    - "pan_left" (проезд камеры — для динамики)

    Чередуй эффекты между сценами.

    Также подготовь SEO-пакет для публикации в YouTube Shorts:
    - "title": короткое цепляющее название до 60 символов.
    - "youtube_description": 2–3 интригующих предложения по теме с ключевыми словами, без воды и просьб о лайках.
    - "hashtags": 5–7 релевантных хештегов (обязательно включи {required_tags}).
    - "pinned_comment": один провокационный или вовлекающий вопрос в закреплённый комментарий, на который зрителю захочется ответить в комментариях.

    Верни строго валидный JSON:
    {{
        "title": "Короткое цепляющее название для YouTube Shorts",
        "youtube_description": "Интригующее описание ролика на 2-3 предложения с ключевыми словами по теме.",
        "hashtags": ["#темнаяпсихология", "#психология", "#манипуляции", "#shorts"],
        "pinned_comment": "Короткий провокационный вопрос зрителям для комментариев?",
        "hook_banner": "КОРОТКИЙ ЗАГОЛОВОК НА ЭКРАН (3–6 слов)",
        "music_track": "{default_track}",
        "voice_profile": "{default_voice}",
        "scenes": [
            {{
                "text": "Чистый текст диктора без цифр и латиницы.",
                "image_prompt": "Detailed vertical 9:16 scene prompt in English ({preset["visual_style"]})",
                "effect": "shake"
            }}
        ]
    }}
    """


def _extract_json_string(raw_text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _parse_script_json(raw_text: str, preset: dict) -> dict:
    data = json.loads(_extract_json_string(raw_text))
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("JSON не содержит массив scenes")

    scenes = []
    for item in raw_scenes:
        text = " ".join(str(item.get("text", "")).split())
        prompt = str(item.get("image_prompt", "")).strip()
        effect = str(item.get("effect", "zoom_in")).strip()
        if effect not in ALLOWED_EFFECTS:
            effect = "zoom_in"
        if text and prompt:
            scenes.append({
                "text": text,
                "image_prompt": prompt,
                "effect": effect,
            })

    if not scenes:
        raise ValueError("Пустой список валидных сцен")

    tracks = getattr(config, "MUSIC_TRACKS", {})
    music_track = str(data.get("music_track", "")).strip()
    if tracks and music_track not in tracks:
        music_track = next(iter(tracks))

    voices = getattr(config, "VOICE_PROFILES", {})
    default_voice = preset.get("default_voice", getattr(config, "DEFAULT_VOICE_PROFILE", "dark_male"))
    voice_profile = str(data.get("voice_profile", "")).strip()
    if voices and voice_profile not in voices:
        voice_profile = default_voice if default_voice in voices else next(iter(voices))

    raw_tags = data.get("hashtags", [])
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.split()

    hashtags = []
    seen_tags = set()
    for tag in list(raw_tags) + list(preset.get("required_hashtags", [])):
        clean_tag = re.sub(r"\s+", "", str(tag).strip())
        if not clean_tag:
            continue
        if not clean_tag.startswith("#"):
            clean_tag = "#" + clean_tag
        lowered = clean_tag.lower()
        if lowered not in seen_tags:
            seen_tags.add(lowered)
            hashtags.append(clean_tag)

    hashtags = hashtags[:8]
    if not any(t.lower() == "#shorts" for t in hashtags):
        hashtags.append("#shorts")

    hook_banner = " ".join(str(data.get("hook_banner") or data.get("title") or "").split())
    youtube_description = " ".join(str(data.get("youtube_description", "")).split())
    pinned_comment = " ".join(str(data.get("pinned_comment", "")).split())

    data["channel"] = preset["name"]
    data["hook_banner"] = hook_banner
    data["music_track"] = music_track
    data["voice_profile"] = voice_profile
    data["youtube_description"] = youtube_description
    data["hashtags"] = hashtags
    data["hashtags_str"] = " ".join(hashtags)
    data["pinned_comment"] = pinned_comment
    data["scenes"] = scenes
    data["full_text"] = " ".join(s["text"] for s in scenes)
    data["image_prompts"] = [s["image_prompt"] for s in scenes]
    return data


def _call_gemini(prompt: str, preset: dict) -> dict:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Не задан GEMINI_API_KEY")

    client = genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=30000),
    )
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )
    return _parse_script_json(response.text, preset)


def _call_groq(prompt: str, preset: dict) -> dict:
    if not config.GROQ_API_KEY:
        raise RuntimeError("Не задан GROQ_API_KEY")

    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Ты режиссёр и сценарист вирусных YouTube Shorts. Отвечай строго валидным JSON объектом.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
        "max_completion_tokens": 4096,
    }

    if "gpt-oss" in config.GROQ_MODEL:
        payload["reasoning_effort"] = "low"

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=35,
    )

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

    content = response.json()["choices"][0]["message"]["content"]
    return _parse_script_json(content, preset)


def generate_script(topic: str, channel: str | None = None) -> dict:
    preset = _get_channel_preset(channel)
    prompt = _build_prompt(topic, preset)
    providers = {
        "gemini": _call_gemini,
        "groq": _call_groq,
    }

    order = (
        ["groq", "gemini"]
        if config.PRIMARY_SCRIPT_PROVIDER == "groq"
        else ["gemini", "groq"]
    )

    errors = []
    for name in order:
        for attempt in range(1, 3):
            try:
                print(f"[SCRIPT] Запрос к {name} (попытка {attempt})...")
                result = providers[name](prompt, preset)
                print(
                    f"[SCRIPT] Раскадровка ({len(result['scenes'])} сцен, "
                    f"трек: {result['music_track']}, голос: {result['voice_profile']}) получена от {name}"
                )
                return result
            except Exception as e:
                print(f"[SCRIPT] {name} попытка {attempt} не удалась: {e}")
                errors.append(f"{name}#{attempt}: {e}")
                if attempt < 2:
                    time.sleep(1.5)

    raise RuntimeError("Оба провайдера не сработали -> " + " | ".join(errors))
