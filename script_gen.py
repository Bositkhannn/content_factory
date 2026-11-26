import json
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


def _build_prompt(topic: str) -> str:
    tracks_block = "\n".join(
        f'    - "{key}" ({desc})'
        for key, desc in config.MUSIC_TRACKS.items()
    )
    # ← изменено: список голосов для выбора сценаристом
    voices_block = "\n".join(
        f'    - "{key}" ({item["description"]})'
        for key, item in config.VOICE_PROFILES.items()
    )

    return f"""
    Создай сценарий и раскадровку для короткого вертикального видео YouTube Shorts на тему: "{topic}".
    Стиль: тёмная психология, холодный, уверенный, без воды. Текст должен звучать как живая речь умного и жёсткого рассказчика, а не как сгенерированная нейросетью статья.

    СТРОГАЯ СТРУКТУРА СЦЕН:
    1. Сцена 1 — ОГЛАВЛЕНИЕ-ХУК + НАУЧНЫЙ ЯКОРЬ (2–4 секунды речи):
       - Начни строго с прямого и чёткого обозначения темы ролика (например: "Как защитить себя от манипулятора?").
       - Сразу после вопроса/темы дай короткую подводку с опорой на авторитет (варьируй формулировки, например: "Существует четыре научно доказанных способа.", "Поведенческая психология выделяет три проверенных приёма.", "Есть четыре подтверждённых экспериментами правила.").
       - Если в теме уже указано число (например, "3 фразы" или "5 причин"), используй ровно это число пунктов. Если числа в теме нет — сделай 3 или 4 пункта.
    2. Следующие сцены — ПО ОДНОЙ СЦЕНЕ НА КАЖДЫЙ ПУНКТ:
       - Каждый пункт начинай чётко со слова-маркера: "Первый.", "Второй.", "Третий.", "Четвёртый." (или "Первое.", "Второе." — согласуй по роду).
       - В каждом пункте 1–2 коротких, острых, конкретных предложения. Без общих слов.
    3. Последняя сцена — ДОМИНАНТНЫЙ ПРИЗЫВ К ПОДПИСКЕ (CTA):
       - НЕ проси и НЕ умоляй подписаться. Запрещены фразы вроде "пожалуйста", "поддержите канал", "ставьте лайк".
       - Построй финал как вызов, укол в самолюбие или рациональный выбор строго под тему этого ролика.
       - Примеры нужной интонации (обязательно адаптируй под текущую тему "{topic}"):
         "Хочешь узнать больше о том, как раскусить манипулятора и не стать его пешкой? Тогда подпишись на канал, чтобы не пропустить новые видео — здесь мы вскрываем всё о тёмной психологии."
         "Остальные так и будут попадаться на этот трюк. Подпишись прямо сейчас, если хочешь видеть скрытые мотивы людей и не пропустить следующие разборы."
       - Никаких упоминаний Telegram, ссылок в описании или лайков — только подписка на канал.

    ЗАПРЕЩЕНО:
    - Канцелярит и ИИ-штампы ("в современном мире", "данный способ", "важно понимать", "является", "не секрет что", "многие люди сталкиваются").
    - Пометки диктору, скобки, эмодзи, хештеги внутри текста сцен.
    - Цифры и латиница внутри текста диктора: все числа пиши строго русскими словами ("четыре", "тридцать", "двадцать процентов").

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

    Верни строго JSON:
    {{
        "title": "Полное цепляющее название для YouTube Shorts",
        "hook_banner": "КОРОТКИЙ ЗАГОЛОВОК НА ЭКРАН (3–6 слов, отражающий суть темы)",
        "music_track": "manipulation",
        "voice_profile": "dark_male",
        "scenes": [
            {{
                "text": "Чистый текст диктора для этой сцены.",
                "image_prompt": "Detailed vertical 9:16 prompt in English in unified dark cinematic style (dark cinematic lighting, moody shadows, hyperrealistic, 8k, no text)",
                "effect": "shake"
            }}
        ]
    }}
    """


def _parse_script_json(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
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

    music_track = str(data.get("music_track", "")).strip()
    if music_track not in config.MUSIC_TRACKS:
        music_track = next(iter(config.MUSIC_TRACKS))

    # ← изменено: валидация профиля голоса
    voice_profile = str(data.get("voice_profile", "")).strip()
    if voice_profile not in config.VOICE_PROFILES:
        voice_profile = config.DEFAULT_VOICE_PROFILE

    hook_banner = " ".join(str(data.get("hook_banner") or data.get("title") or "").split())

    data["hook_banner"] = hook_banner
    data["music_track"] = music_track
    data["voice_profile"] = voice_profile
    data["scenes"] = scenes
    data["full_text"] = " ".join(s["text"] for s in scenes)
    data["image_prompts"] = [s["image_prompt"] for s in scenes]
    return data


def _call_gemini(prompt: str) -> dict:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Не задан GEMINI_API_KEY")

    client = genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=20000),
    )
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )
    return _parse_script_json(response.text)


def _call_groq(prompt: str) -> dict:
    if not config.GROQ_API_KEY:
        raise RuntimeError("Не задан GROQ_API_KEY")

    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Ты режиссёр и сценарист вирусных YouTube Shorts по тёмной психологии. Отвечай строго валидным JSON объектом.",
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
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

    content = response.json()["choices"][0]["message"]["content"]
    return _parse_script_json(content)


def generate_script(topic: str) -> dict:
    prompt = _build_prompt(topic)
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
        try:
            print(f"[SCRIPT] Запрос к {name}...")
            result = providers[name](prompt)
            # ← изменено: печатаем выбранный голос
            print(
                f"[SCRIPT] Раскадровка ({len(result['scenes'])} сцен, "
                f"трек: {result['music_track']}, голос: {result['voice_profile']}) "
                f"получена от {name}"
            )
            return result
        except Exception as e:
            print(f"[SCRIPT] {name} не сработал: {e}")
            errors.append(f"{name}: {e}")

    raise RuntimeError("Оба провайдера не сработали -> " + " | ".join(errors))