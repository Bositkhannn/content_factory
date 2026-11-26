import os
import random
import time
import urllib.parse
import requests
import config


def _build_request(prompt: str, seed: int) -> tuple[str, dict]:
    encoded_prompt = urllib.parse.quote(prompt)
    if config.POLLINATIONS_API_KEY:
        url = (
            f"https://gen.pollinations.ai/image/{encoded_prompt}"
            f"?width={config.IMAGE_WIDTH}&height={config.IMAGE_HEIGHT}"
            f"&model=flux&seed={seed}&nologo=true"
        )
        headers = {"Authorization": f"Bearer {config.POLLINATIONS_API_KEY}"}
        return url, headers

    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={config.IMAGE_WIDTH}&height={config.IMAGE_HEIGHT}"
        f"&model=flux&seed={seed}&nologo=true"
    )
    return url, {}


def generate_images(prompts: list[str], output_folder: str, on_progress=None) -> None:
    total = len(prompts)
    for index, prompt in enumerate(prompts, start=1):
        file_path = os.path.join(output_folder, f"scene_{index:02d}.png")
        saved = False

        for attempt in range(1, 5):
            seed = random.randint(1, 999999)
            url, headers = _build_request(prompt, seed)
            try:
                print(f"[IMG] Кадр {index}/{total}, попытка {attempt}...")
                response = requests.get(url, headers=headers, timeout=90)
                content_type = response.headers.get("content-type", "")

                if response.status_code == 200 and content_type.startswith("image/"):
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    print(f"[IMG] Кадр {index}/{total} сохранен")
                    saved = True
                    break

                print(f"[IMG] Ответ {response.status_code} ({content_type})")
                wait_time = 15 if response.status_code == 429 else 5
                time.sleep(wait_time)
            except requests.RequestException as e:
                print(f"[IMG] Ошибка сети: {e}")
                time.sleep(5)

        if not saved:
            print(f"[IMG] Не удалось скачать кадр {index}/{total}")

        if on_progress:
            on_progress(index, total)

        if index < total:
            delay = config.IMAGE_DELAY_SECONDS if config.POLLINATIONS_API_KEY else 12
            time.sleep(delay)