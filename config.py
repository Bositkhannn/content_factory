import os
import shutil
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.8-flash"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-120b"

PRIMARY_SCRIPT_PROVIDER = "groq"

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")

VOICE_NAME = "ru-RU-SvetlanaNeural"
DEFAULT_VOICE_PROFILE = "dark_male"
ASSETS_MODELS_DIR = os.path.join(BASE_DIR, "assets", "models")
SILERO_MODEL_URL = "https://models.silero.ai/models/tts/ru/v4_ru.pt"
SILERO_MODEL_PATH = os.path.join(ASSETS_MODELS_DIR, "v4_ru.pt")
DEFAULT_VOICE_PROFILE = "dark_male"

VOICE_PROFILES = {
    "dark_male": {
        "engine": "silero",
        "speaker": "eugene",
        "af": "asetrate=48000*0.93,aresample=44100,atempo=1.02,bass=g=4:f=110",
        "description": "Низкий тяжёлый мужской голос — тёмная психология, угрозы, манипуляции, власть",
    },
    "calm_male": {
        "engine": "silero",
        "speaker": "aidar",
        "af": "aresample=44100,atempo=0.96",
        "description": "Спокойный рассудительный мужской голос — тайны истории, стоицизм, факты, аналитика",
    },
    "sharp_female": {
        "engine": "edge",
        "speaker": "ru-RU-SvetlanaNeural",
        "af": "aresample=44100,atempo=1.08,treble=g=2",
        "description": "Быстрый холодный женский голос — резкие разоблачения, жёсткая правда, провокации",
    },
    "emotional_female": {
        "engine": "silero",
        "speaker": "kseniya",
        "af": "aresample=44100,atempo=1.02",
        "description": "Выразительный эмоциональный женский голос — отношения, привязанность, качели",
    },
    "calm_female": {
        "engine": "silero",
        "speaker": "baya",
        "af": "aresample=44100,atempo=0.94",
        "description": "Мягкий спокойный женский голос — антистресс, сон, одиночество, философия",
    },
}

IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_DELAY_SECONDS = 4

VIDEO_FPS = 24
FFMPEG_THREADS = 2
MUSIC_VOLUME = 0.16

OUTPUT_DIR = "output"
ASSETS_MUSIC_DIR = os.path.join(BASE_DIR, "assets", "music")

MUSIC_TRACKS = {
    "manipulation": "Холодная манипуляция: тиканье и глубокий бас — контроль, скрытые приёмы, психологическое давление",
    "noir_piano": "Мрачное нуарное пианино — жёсткая правда, экзистенциализм, разочарование, одиночество",
    "neon_noir": "Неоновый нуар — холодное превосходство, отстранённость, уверенность, теневой образ",
    "hidden_threat": "Скрытая угроза — тревожный саспенс, признаки манипуляторов, пугающие факты",
    "mind_game": "Интеллектуальная игра — стратегия, чтение людей, статус, власть и холодный расчёт",
    "dark_underground": "Замедленный тёмный андеграунд — резкие агрессивные хуки, провокация, жёсткая динамика",
}


def get_ffmpeg_path() -> str:
    local_bin = os.path.join(BASE_DIR, "ffmpeg.exe")
    if os.path.isfile(local_bin):
        return local_bin
    return shutil.which("ffmpeg") or "ffmpeg"


def get_ffprobe_path() -> str:
    local_bin = os.path.join(BASE_DIR, "ffprobe.exe")
    if os.path.isfile(local_bin):
        return local_bin
    return shutil.which("ffprobe") or "ffprobe"