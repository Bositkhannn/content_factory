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
        "af": "aresample=48000,asetrate=48000*0.96,aresample=44100,highpass=f=75,bass=g=3:f=130,equalizer=f=3200:t=q:w=1.5:g=-3.5,lowpass=f=10500,aecho=0.85:0.88:120|210:0.18|0.09",
        "description": "Низкий глубокий мужской голос с лёгким эхом — тёмная психология, манипуляции, власть",
    },
    "calm_male": {
        "engine": "silero",
        "speaker": "aidar",
        "af": "aresample=48000,asetrate=48000*0.97,aresample=44100,highpass=f=80,bass=g=2:f=140,equalizer=f=3400:t=q:w=1.5:g=-3,lowpass=f=11000,aecho=0.88:0.88:130:0.14",
        "description": "Спокойный рассудительный мужской голос — тайны истории, стоицизм, факты, аналитика",
    },
    "sharp_female": {
        "engine": "edge",
        "speaker": "ru-RU-SvetlanaNeural",
        "af": "aresample=44100,highpass=f=85,equalizer=f=3500:t=q:w=1.5:g=-2,aecho=0.88:0.88:120:0.14",
        "description": "Чёткий холодный женский голос с лёгким эхом — резкие разоблачения, жёсткая правда",
    },
    "emotional_female": {
        "engine": "silero",
        "speaker": "kseniya",
        "af": "aresample=44100,highpass=f=85,equalizer=f=3200:t=q:w=1.5:g=-3,lowpass=f=11500,aecho=0.88:0.88:125:0.15",
        "description": "Живой выразительный женский голос — отношения, привязанность, эмоциональные качели",
    },
    "calm_female": {
        "engine": "silero",
        "speaker": "baya",
        "af": "aresample=48000,asetrate=48000*0.98,aresample=44100,highpass=f=85,bass=g=2:f=150,equalizer=f=3200:t=q:w=1.5:g=-3,lowpass=f=11000,aecho=0.85:0.88:140:0.16",
        "description": "Мягкий спокойный женский голос с лёгким эхом — антистресс, сон, одиночество, философия",
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
