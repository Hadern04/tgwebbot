import requests
from bs4 import BeautifulSoup
import json

st_accept = "text/html"
st_useragent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15"
headers = {
    "Accept": st_accept,
    "User-Agent": st_useragent
}


def fetch_page(url, headers):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Ошибка загрузки страницы: {e}")
        return None


def parse_food_data(src):
    soup = BeautifulSoup(src, 'lxml')
    allfood = soup.findAll('div', class_='eael-accordion-list')
    data = []
    for category in allfood:
        category_title = category.find('span', class_='eael-accordion-tab-title')
        items = []
        if category_title:
            print(f'Обработка категории {category_title.string}...')
            food_items = category.findAll('div', class_='product-wrapper')
            for food in food_items:
                food_url = food.find('a', class_='product-image-link')['href']
                food_src = fetch_page(food_url, headers)
                food_soup = BeautifulSoup(food_src, 'lxml')
                title = food_soup.find('h1', class_='product_title').string
                img = food_soup.find('img', class_='wp-post-image')['src']
                description_title = food_soup.find('div', class_='wc-tab-inner')
                description = description_title.get_text(separator='\n', strip=True)
                items.append({"title": title.strip(), "image": img, "description": description})
        data.append({"category": category_title.string, "items": items})
    print("Обработка завершена. Меню было добавлено в файл menu.json")
    with open("menu.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


url = "https://prostovegan.ru/cafe/"
src = fetch_page(url, headers)
if src:
    parse_food_data(src)
