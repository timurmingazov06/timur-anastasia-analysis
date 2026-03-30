import os
import urllib.parse
import requests
import random
import string
import re
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from PIL import Image, ImageFile
import cv2
import numpy as np

# Настройки
FIXED_WIDTH = 1920
FIXED_HEIGHT = 1080
THREADS = 5
ImageFile.LOAD_TRUNCATED_IMAGES = True


def generate_random_filename(path_img, extension=".jpg"):
    """Генерирует уникальное имя файла"""
    while True:
        filename = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        full_path = os.path.join(path_img, filename + extension)
        if not os.path.exists(full_path):
            return filename + extension


def parser_url(key):
    """Парсит URL изображений из Google"""
    encoded_key = urllib.parse.quote(key)
    url = f"https://www.google.com/search?q={encoded_key}&tbm=isch"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            pattern = r'\["(https://[^"]+\.(?:jpg|jpeg|png|webp))"'
            return list(set(re.findall(pattern, response.text)))
        return []
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return []


def download_image(link, path_img):
    """Скачивает и сохраняет изображение"""
    try:
        response = requests.get(link, stream=True, timeout=15)
        if response.status_code == 200:
            ext = os.path.splitext(urllib.parse.urlparse(link).path)[1][:4].lower()
            ext = ext if ext in ['.jpg', '.jpeg', '.png', '.webp'] else '.jpg'

            filename = generate_random_filename(path_img, ext)
            save_path = os.path.join(path_img, filename)

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            if os.path.getsize(save_path) < 50 * 1024:
                os.remove(save_path)
                return None
            return save_path
    except Exception as e:
        return None


def add_bokeh_effect(img):
    """Добавляет эффект боке"""
    img_np = np.array(img)
    blurred = cv2.GaussianBlur(img_np, (99, 99), 30)
    return Image.fromarray(blurred)


def process_image(image_path):
    """Основная обработка изображения"""
    try:
        img = Image.open(image_path)

        # Сохраняем пропорции
        width_percent = FIXED_HEIGHT / float(img.height)
        new_width = int(float(img.width) * width_percent)

        # Ресайз с сохранением пропорций
        img = img.resize((new_width, FIXED_HEIGHT), Image.LANCZOS)

        # Создаем фон 1920x1080
        if new_width > FIXED_WIDTH:
            # Обрезаем по центру
            left = (new_width - FIXED_WIDTH) // 2
            img = img.crop((left, 0, left + FIXED_WIDTH, FIXED_HEIGHT))
        elif new_width < FIXED_WIDTH:
            # Добавляем размытый фон
            bg = add_bokeh_effect(img.resize((FIXED_WIDTH, FIXED_HEIGHT), Image.LANCZOS))
            offset = (FIXED_WIDTH - new_width) // 2
            bg.paste(img, (offset, 0))
            img = bg

        # Сохраняем с оптимизацией
        img.convert('RGB').save(image_path, quality=85, optimize=True)
    except Exception as e:
        print(f"Ошибка обработки {image_path}: {e}")


def post_processing(path):
    """Постобработка всех изображений в папке"""
    valid_ext = ('.jpg', '.jpeg', '.png', '.webp')

    for root, _, files in os.walk(path):
        # Конвертируем в JPG
        for file in files:
            if file.lower().endswith(('.png', '.webp')):
                try:
                    img = Image.open(os.path.join(root, file)).convert('RGB')
                    new_name = generate_random_filename(root, '.jpg')
                    img.save(os.path.join(root, new_name))
                    os.remove(os.path.join(root, file))
                except:
                    pass

        # Обрабатываем все изображения
        images = [f for f in files if f.lower().endswith(valid_ext)]
        for file in tqdm(images, desc=f"Обработка {root}"):
            process_image(os.path.join(root, file))


def main():
    """Основная функция"""
    if not os.path.exists('Key.txt'):
        print("Создайте файл Key.txt с поисковыми запросами!")
        return

    with open('Key.txt', 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    for folder_number, line in enumerate(lines, 1):
        folder_name = str(folder_number)
        os.makedirs(folder_name, exist_ok=True)

        queries = [q.strip() for q in line.split(',') if q.strip()]
        print(f"\nПапка {folder_number}: Обработка запросов: {', '.join(queries)}")

        total_downloaded = 0
        for query in queries:
            print(f"\nПоиск: '{query}'")
            links = parser_url(query)

            if links:
                with ThreadPoolExecutor(THREADS) as executor:
                    results = list(tqdm(
                        executor.map(lambda url: download_image(url, folder_name), links),
                        total=len(links),
                        desc=f"Скачивание '{query[:15]}...'"
                    ))

                downloaded = sum(1 for result in results if result is not None)
                total_downloaded += downloaded
                print(f"Скачано изображений: {downloaded}")
            else:
                print("Нет результатов для этого запроса")

        if total_downloaded > 0:
            print("\nПостобработка изображений...")
            post_processing(folder_name)
            print(f"Готово! Обработано изображений: {total_downloaded}")
        else:
            print("Нет скачанных изображений для обработки")

        print("=" * 50)


if __name__ == "__main__":
    main()
