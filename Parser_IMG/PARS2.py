import os
import urllib.parse
import requests
import random
import string
import re
import time
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from PIL import Image

# -- ПАРАМЕТРЫ --
FIXED_WIDTH = 1920
FIXED_HEIGHT = 1080
MIN_WIDTH = 800
MIN_HEIGHT = 600
THREADS = 5
REQUEST_DELAY = 1.1

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/114.0.0.0 Safari/537.36'
}

# --- ТРАНСЛИТ ---
def transliterate(text):
    dictionary = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m',
        'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh',
        'щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
    result = ''
    for ch in text:
        lower = ch.lower()
        s = dictionary.get(lower, ch)
        result += s.upper() if ch.isupper() else s
    return result

# --- Google Images (regex) ---
def parser_url_google(query):
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded_query}&tbm=isch"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        time.sleep(REQUEST_DELAY)
        if response.status_code != 200:
            print(f"Google: Ошибка загрузки страницы {response.status_code} для '{query}'")
            return []
        pattern = r'\["(https?://[^"]+\.(?:jpg|jpeg|png|webp|gif))"'
        links = re.findall(pattern, response.text)
        print(f"Google: найдено {len(links)} изображений для '{query}'")
        return list(set(links))
    except Exception as e:
        print(f"Google: Ошибка для '{query}': {e}")
        return []

# --- Проверка/масштабирование изображения через PIL ---
def is_valid_image(path):
    try:
        with Image.open(path) as img:
            w, h = img.size
            return ((w >= MIN_WIDTH and h >= MIN_HEIGHT) or (w >= MIN_HEIGHT and h >= MIN_WIDTH))
    except:
        return False

def resize_image(path):
    try:
        with Image.open(path) as img:
            img = img.convert('RGB')
            aspect = img.width / img.height
            fixed_aspect = FIXED_WIDTH / FIXED_HEIGHT
            if aspect > fixed_aspect:
                new_width = FIXED_WIDTH
                new_height = int(FIXED_WIDTH / aspect)
            else:
                new_height = FIXED_HEIGHT
                new_width = int(FIXED_HEIGHT * aspect)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            img.save(path, quality=85)
            return True
    except Exception as e:
        print(f"Ошибка ресайза: {e}")
        return False

def generate_random_filename(path_img, extension=".jpg"):
    while True:
        filename = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        save_path = os.path.join(path_img, filename + extension)
        if not os.path.exists(save_path):
            return filename + extension

def download_image(link, path_img):
    link = link.strip()
    decoded = urllib.parse.unquote(link)
    for _ in range(3):
        try:
            _, ext = os.path.splitext(decoded)
            ext = ext.lower()
            if ext not in [".jpg",".jpeg",".png",".webp",".gif"]:
                ext = ".jpg"
            filename = generate_random_filename(path_img, ext)
            save_path = os.path.join(path_img, filename)
            resp = requests.get(decoded, headers=HEADERS, stream=True, timeout=10)
            if resp.status_code == 200:
                with open(save_path,'wb') as f:
                    for chunk in resp.iter_content(1024):
                        f.write(chunk)
                if os.path.getsize(save_path) < 30*1024:
                    os.remove(save_path)
                    return
                if not is_valid_image(save_path):
                    os.remove(save_path)
                    return
                resize_image(save_path)
                return
        except Exception as e:
            time.sleep(1)

def postprocess_images(path_img):
    for fn in os.listdir(path_img):
        filepath = os.path.join(path_img, fn)
        if os.path.isfile(filepath) and ('.' not in fn or fn.endswith('.img')):
            os.remove(filepath)
        if fn.lower().endswith(('.png','.webp')):
            try:
                img = Image.open(filepath).convert('RGB')
                nfn = generate_random_filename(path_img,'.jpg')
                img.save(os.path.join(path_img, nfn), quality=85)
                os.remove(filepath)
            except Exception as e:
                print(f"Ошибка преобразования {fn}: {e}")

def download_images_for_queries(queries, path_img):
    os.makedirs(path_img, exist_ok=True)
    all_links = []

    for query in queries:
        links_this_query = []
        query_lat = transliterate(query)
        print(f"\nGoogle: '{query}'")
        links_this_query.extend(parser_url_google(query))
        if query_lat.lower() != query.lower():
            print(f"Google: '{query_lat}'")
            links_this_query.extend(parser_url_google(query_lat))
        print(f"Найдено всего: {len(set(links_this_query))}")
        all_links.extend(links_this_query)
    all_links = list(set(all_links))
    print(f"\nИтого уникальных ссылок: {len(all_links)}")
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        list(tqdm(executor.map(lambda link: download_image(link, path_img), all_links),
            total=len(all_links), desc="Скачивание изображений"))

def main():
    if not os.path.exists('Key.txt'):
        print("Key.txt не найден!")
        return
    with open('Key.txt','r',encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        print("Key.txt пуст!")
        return
    for idx, line in enumerate(lines,1):
        queries = [q.strip() for q in line.split(',') if q.strip()]
        folder = str(idx)
        print(f"\n===== НАБОР {idx}: {', '.join(queries)} =====")
        download_images_for_queries(queries, folder)
        print("Постобработка...")
        postprocess_images(folder)
        print(f"-- ГОТОВО: {folder} --\n" + "="*50)
    print("\nВсе запросы обработаны. Скрипт завершил работу.")

if __name__ == "__main__":
    main()
