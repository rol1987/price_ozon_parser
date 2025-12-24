import pandas as pd
import time, os, logging, random
from xml.dom import minidom
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Отключаем логирование
logging.getLogger('playwright').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

import os
from playwright.sync_api import sync_playwright

def get_stealth_driver_chrome(opt=None):
    """Упрощенная версия для отладки"""
    playwright = sync_playwright().start()
    
    # Минимальный набор аргументов
    args = [
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--start-maximized"
    ]
    
    # Просто запускаем Chrome без сложных настроек
    browser = playwright.chromium.launch(
        headless=True,
        channel="chrome",
        args=args
    )
    
    # Простой контекст
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        locale='ru-RU'
    )
    
    page = context.new_page()
    
    # Только самый важный stealth-скрипт
    page.add_init_script("""
        delete Object.getPrototypeOf(navigator).webdriver;
        window.navigator.chrome = { runtime: {} };
    """)
    
    return page, browser, playwright

def create_yml_for_all_articles(articles_data):
    """Создает один YML файл со всеми артикулами"""
    from xml.etree import ElementTree as ET
    from xml.dom.minidom import Document
    
    # Используем minidom для правильного создания тегов
    doc = Document()
    
    # Создаем корневой элемент
    yml_catalog = doc.createElement('yml_catalog')
    yml_catalog.setAttribute('date', time.strftime('%Y-%m-%d %H:%M'))
    doc.appendChild(yml_catalog)
    
    # Создаем элемент shop
    shop = doc.createElement('shop')
    yml_catalog.appendChild(shop)
    
    # Базовые элементы shop
    name = doc.createElement('name')
    name.appendChild(doc.createTextNode('SONOX'))
    shop.appendChild(name)
    
    company = doc.createElement('company')
    company.appendChild(doc.createTextNode(''))
    shop.appendChild(company)
    
    url = doc.createElement('url')
    url.appendChild(doc.createTextNode('https://kit8576.yastore.yandex.ru'))
    shop.appendChild(url)
    
    # Валюты
    currencies = doc.createElement('currencies')
    shop.appendChild(currencies)
    
    currency = doc.createElement('currency')
    currency.setAttribute('id', 'RUB')
    currency.setAttribute('rate', '1')
    currencies.appendChild(currency)
    
    # Категории
    categories = doc.createElement('categories')
    categories.appendChild(doc.createTextNode(''))
    shop.appendChild(categories)
    
    # Предложения
    offers = doc.createElement('offers')
    shop.appendChild(offers)
    
    # Добавляем все артикулы
    for article_data in articles_data:
        article = article_data['article']
        price = article_data['price']
        
        # Создаем offer для артикула
        offer = doc.createElement('offer')
        offer.setAttribute('id', f'mp-{article}')
        offer.setAttribute('available', 'true')
        offers.appendChild(offer)
        
        # Цена
        price_elem = doc.createElement('price')
        price_text = doc.createTextNode(str(price) if price else '0')
        price_elem.appendChild(price_text)
        offer.appendChild(price_elem)
        
        # Param с Артикулом МП
        param_mp = doc.createElement('param')
        param_mp.setAttribute('name', 'Артикул МП')
        param_mp_text = doc.createTextNode(str(article))
        param_mp.appendChild(param_mp_text)
        offer.appendChild(param_mp)
    
    # Красивое форматирование
    pretty_xml = doc.toprettyxml(indent="  ", encoding='utf-8')
    
    return pretty_xml

# Основной код
cwd = os.path.dirname(__file__)
full_path = os.path.join(cwd, 'art.xlsx')  

df = pd.read_excel(full_path, usecols=[0], header=None)
values_list = df[0].dropna().tolist()

print(f"Найдено {len(values_list)} артикулов")

opt = "--force-device-scale-factor=1"
page, browser, playwright = get_stealth_driver_chrome(opt)

# Создаем папку для XML файлов
xml_folder = os.path.join(cwd, 'xml_files')
os.makedirs(xml_folder, exist_ok=True)

# Список для хранения данных по всем артикулам
all_articles_data = []

# ЦИКЛ ПО ВСЕМ АРТИКУЛАМ
for idx, article in enumerate(values_list):
# for idx, article in enumerate(values_list[0:10]):  # Тестово 10 артикулов
    try:
        print(f"\n[{idx+1}/{len(values_list)}] Обрабатываю артикул: {article}")
        
        url = f'https://www.ozon.ru/product/{article}/'
        
        page.goto(url, wait_until="domcontentloaded", timeout=10000)
        time.sleep(2)

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')

        # Находим ВСЕ span на странице
        all_spans = soup.find_all('span')

        # Создаем список для хранения информации о span
        span_list = []

        # Записываем все span в список
        for span in all_spans:
            span_list.append(span.text)

        # if str(article) == '2321380998':
            # print(span_list)
            # time.sleep(111111)
            
        # Ищем цену
        price = 0  # Значение по умолчанию
        for i, item in enumerate(span_list):
            if item and 'c Ozon Картой' == item:
                # Проверяем предыдущий элемент
                if i > 0:
                    previous_item = span_list[i-1]
                    
                    # Проверяем, содержатся ли цифры
                    if previous_item and any(char.isdigit() for char in previous_item):
                        # Удаляем всё, кроме цифр
                        only_digits = ''.join(filter(str.isdigit, previous_item))
                        
                        if only_digits:  # Проверяем, что не пустая строка
                            price = str(only_digits)
                            print(f"  Найдена цена: {price}")
                            break
        
        # Добавляем данные артикула в общий список
        all_articles_data.append({
            'article': article,
            'price': price,
            'status': 'успешно'
        })
        
        print(f"  Артикул {article} обработан, цена: {price}")
        
    except Exception as e:
        print(f"Ошибка при обработке артикула {article}: {e}")
        
        # Добавляем артикул с ошибкой
        all_articles_data.append({
            'article': article,
            'price': 0,
            'status': f'ошибка: {str(e)[:50]}'
        })
        continue

print("\nВсе артикулы обработаны!")

# Создаем один XML файл со всеми артикулами
try:
    yml_content = create_yml_for_all_articles(all_articles_data)
    
    # Сохраняем XML файл
    yml_filename = f'all_articles_{time.strftime("%Y%m%d_%H%M")}.xml'
    yml_path = os.path.join(xml_folder, yml_filename)
    
    with open(yml_path, 'wb') as yml_file:
        yml_file.write(yml_content)
    
    print(f"\n✅ Единый XML файл создан: {yml_filename}")
    print(f"   Сохранено {len(all_articles_data)} артикулов")
    
except Exception as e:
    print(f"Ошибка при создании XML файла: {e}")

# Закрываем браузер
page.close()
browser.close()
playwright.stop()

# Выводим статистику
success_count = sum(1 for item in all_articles_data if item['price'] > 0)
error_count = sum(1 for item in all_articles_data if item['price'] == 0)

print(f"\n📊 СТАТИСТИКА:")
print(f"   Всего артикулов: {len(all_articles_data)}")
print(f"   С успешной ценой: {success_count}")
print(f"   Без цены/с ошибкой: {error_count}")
print(f"\nXML файлы сохранены в папке: {xml_folder}")