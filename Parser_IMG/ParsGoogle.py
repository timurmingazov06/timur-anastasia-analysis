import os
import urllib.parse
import requests
import random
import string
import re
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from PIL import Image

FIXED_HEIGHT = 1080
FIXED_WIDTH = 1920
THREADS = 5  # Количество потоков


def generate_random_filename(path_img, extension=".jpg"):
    """Генерирует случайное имя файла (8 символов: буквы + цифры) и проверяет уникальность."""
    while True:
        filename = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        save_path = os.path.join(path_img, filename + extension)
        if not os.path.exists(save_path):
            return filename + extension


def parser_url(key):
    """Парсит ссылки на изображения из Google."""
    encoded_key = urllib.parse.quote(key)
    url = f"https://www.google.com/search?q={encoded_key}&newwindow=1&udm=2&source=lnt&tbs=isz:l&biw=1920&bih=1075&dpr=1"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code != 200:
        print(f"Ошибка при загрузке страницы. Код состояния: {response.status_code}")
        return []

    text = response.text
    pattern_imgurl = r'href="https://www\.google\.com/imgres\?[^"]*?imgurl=([^&]*)'
    pattern_alternate = r'\["(https://[^"]*\.(?:jpg|jpeg|webp|png|gif))"'

    links_imgurl = [urllib.parse.unquote(link) for link in re.findall(pattern_imgurl, text)]
    links_alternate = re.findall(pattern_alternate, text)
    links = list(set(links_imgurl + links_alternate))

    print(f"Найдено {len(links)} изображений для запроса: '{key}'")
    return links


def download_image(link, path_img):
    """Скачивает изображение по ссылке с рандомным названием."""
    link = link.strip()
    decoded_url = urllib.parse.unquote(link)

    try:
        _, file_extension = os.path.splitext(decoded_url)
        file_extension = urllib.parse.unquote(file_extension.split('?')[0]).lower()

        if file_extension not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            file_extension = ".jpg"  # Если расширение неизвестно, сохраняем как JPG

        filename = generate_random_filename(path_img, file_extension)
        save_path = os.path.join(path_img, filename)

        response = requests.get(decoded_url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)

            if os.path.getsize(save_path) < 30 * 1024:
                os.remove(save_path)

    except Exception as e:
        print(f"Ошибка при загрузке {link}: {e}")


def post_image(path_img):
    """Обрабатывает изображения после загрузки."""
    # Удаляем пустые файлы
    for filename in os.listdir(path_img):
        filepath = os.path.join(path_img, filename)
        if os.path.isfile(filepath) and ('.' not in filename or filename.endswith('.img')):
            os.remove(filepath)

    # Конвертируем PNG и WEBP в JPG
    n = sum(1 for _, _, files in os.walk(path_img) for f in files if f.endswith(('.png', '.webp')))
    if n > 0:
        with tqdm(total=n, desc="Конвертируем в JPG", unit='pic') as pbar:
            for root, _, files in os.walk(path_img):
                for file in files:
                    if file.endswith(('.png', '.webp')):
                        try:
                            img = Image.open(os.path.join(root, file)).convert('RGB')
                            new_filename = generate_random_filename(root, ".jpg")
                            img.save(os.path.join(root, new_filename))
                            os.remove(os.path.join(root, file))
                            pbar.update()
                        except Exception as e:
                            print(f"Ошибка при конвертации {file}: {e}")

    # Изменяем размер изображений
    n_files = sum(len(files) for _, _, files in os.walk(path_img))
    with tqdm(total=n_files, desc="Изменение размеров", unit='pic') as pbar:
        for root, _, files in os.walk(path_img):
            for file in files:
                try:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        img = Image.open(os.path.join(root, file))
                        hpercent = FIXED_HEIGHT / float(img.size[1])
                        wsize = int(float(img.size[0]) * hpercent)
                        img = img.resize((wsize, FIXED_HEIGHT))
                        img.save(os.path.join(root, file))
                except Exception as e:
                    print(f"Ошибка при изменении размера {file}: {e}")
                finally:
                    pbar.update()


def main():
    """Основная функция программы."""
    if not os.path.exists('Key.txt'):
        print("Файл 'Key.txt' не найден!")
        return

    with open('Key.txt', 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    if not lines:
        print("Файл 'Key.txt' пустой!")
        return

    for folder_num, line in enumerate(lines, 1):
        path_img = str(folder_num)
        os.makedirs(path_img, exist_ok=True)
        queries = [q.strip() for q in line.split(',') if q.strip()]

        print(f"\nОбработка папки {folder_num}: {', '.join(queries)}")

        for query in queries:
            print(f"\nПарсим запрос: '{query}'")
            links = parser_url(query)
            if not links:
                continue

            # Ограниченный многопоточный запуск (до 5 потоков)
            with ThreadPoolExecutor(max_workers=THREADS) as executor:
                list(tqdm(executor.map(lambda link: download_image(link, path_img), links),
                          total=len(links), desc="Скачивание"))

        print(f"\nПостобработка изображений в папке {folder_num}")
        post_image(path_img)
        print(f"\nГотово для папки {folder_num}")
        print("=" * 50)

    print("\n Все запросы обработаны. Скрипт завершает работу.")


if __name__ == "__main__":
    main()
