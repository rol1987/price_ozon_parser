import pandas as pd
import time, os, logging, random, schedule, datetime, threading, sys, requests, base64
from xml.dom import minidom
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# Отключаем логирование
logging.getLogger('playwright').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Флаг для отслеживания выполнения
parsing_in_progress = False

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

def execute_parsing():
    """Основная логика парсинга"""
    global parsing_in_progress
    
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*60}")
        print(f"🚀 Запуск парсера: {current_time}")
        print(f"{'='*60}")
        
        # Основной код парсинга
        cwd = os.path.dirname(__file__)
        full_path = os.path.join(cwd, 'art.xlsx')  
        
        df = pd.read_excel(full_path, usecols=[0], header=None)
        values_list = df[0].dropna().tolist()
        
        print(f"Найдено {len(values_list)} артикулов")
        
        opt = "--force-device-scale-factor=1"
        page, browser, playwright = get_stealth_driver_chrome(opt)
        

        
        # Список для хранения данных по всем артикулам
        all_articles_data = []
        
        # ЦИКЛ ПО ВСЕМ АРТИКУЛАМ
        for idx, article in enumerate(values_list[0:1]):
        # for idx, article in enumerate(values_list):
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
            yml_filename = 'all_articles.xml'
            cwd = os.path.dirname(__file__)
            # yml_filename = f'all_articles_{time.strftime("%Y%m%d_%H%M")}.xml'
            yml_path = os.path.join(cwd, yml_filename)
            
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
        
        print(f"\n✅ Парсинг успешно завершен в {datetime.datetime.now().strftime('%H:%M:%S')}")










# _________________________________________________________________________________________________

        def upload_to_github(f_path, token, repo_owner, repo_name):
            
            # Проверяем существование файла
            time.sleep(3)
            if not os.path.exists(f_path):
                print(f"❌ Файл не найден: {f_path}")
                return None
            

            repo_path = os.path.basename(f_path)

            # repo_path = "all_articles.xml"


            # Читаем файл
            with open(f_path, 'rb') as file:
                content = file.read()

            
            # Кодируем в base64
            encoded_content = base64.b64encode(content).decode('utf-8')
            
            # URL API GitHub
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{repo_path}"
            # print(url)
            # Заголовки
            headers = {
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}"
                    }
                        
            # Проверяем, существует ли файл
            response = requests.get(url, headers=headers)
            sha = None
            print(111, response.status_code)
            if response.status_code == 200:
                sha = response.json().get("sha")
                commit_msg = f"Update {os.path.basename(f_path)}"
            else:
                commit_msg = f"Add {os.path.basename(f_path)}"
            
            # Данные для загрузки
            data = {

                "message": commit_msg,
                "content": encoded_content,
                "branch": "main"
            }
            
            if sha:
                data["sha"] = sha
            
            # Загружаем
            response = requests.put(
                url=url, 
                headers=headers,  # заголовки с метаинформацией
                json=data         # данные запроса (тело запроса)
            )
            print(222, response.status_code)

                    


        if __name__ == "__main__":
            # === НАСТРОЙКИ ДЛЯ РЕПОЗИТОРИЯ ===
            TOKEN = "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"  # токен
            REPO_OWNER = "rol1987"  # username
            REPO_NAME = "price_ozon_parser"  # репозиторий

            # === УКАЖИТЕ ПУТЬ К ВАШЕМУ XML ФАЙЛУ ===
            f_path = yml_path  # Замените на ваш путь
            
            # === ЗАГРУЗКА ФАЙЛА ===
            print("=" * 50)
            print(f"ЗАГРУЗКА В РЕПОЗИТОРИЙ: {REPO_OWNER}/{REPO_NAME}")
            print("=" * 50)
            
            # Проверяем файл
            if not os.path.exists(f_path):
                print(f"❌ Файл не найден: {f_path}")
                print("Проверьте правильность пути.")
            else:
                # Загружаем файл
                url = upload_to_github(f_path, TOKEN, REPO_OWNER, REPO_NAME)
                
                if url:
                    print("\n✅ Готово! Файл доступен по ссылке:")
                    print(f"{url}")

# _________________________________________________________________________________________________











        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении парсинга: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        parsing_in_progress = False

def run_parser_job():
    """Запуск парсера в отдельном потоке"""
    global parsing_in_progress
    
    if parsing_in_progress:
        print("Парсинг уже выполняется, пропускаю запуск...")
        return
    
    parsing_in_progress = True
    
    # Запускаем в отдельном потоке, чтобы не блокировать планировщик
    thread = threading.Thread(target=execute_parsing)
    thread.daemon = True
    thread.start()

def input_listener():
    """Поток для прослушивания ввода пользователя - просто ждет Enter"""
    while True:
        try:
            # Просто ждем Enter
            input("\nНажмите Enter для принудительного запуска парсера или Ctrl+C для выхода...")
            run_parser_job()
        except KeyboardInterrupt:
            print("\nЗавершение работы сервиса...")
            os._exit(0)
        except:
            break

if __name__ == "__main__":
    # Настраиваем расписание
    schedule.every().day.at("06:00").do(run_parser_job)
    
    print("="*60)
    print("Сервис ежедневного парсинга Ozon запущен")
    print(f"Текущее время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Следующий автоматический запуск в 6:00 утра")
    print("="*60)
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1].lower() == "now":
        print("\nЗапуск парсера немедленно...")
        run_parser_job()
    
    # Запускаем поток для ввода
    input_thread = threading.Thread(target=input_listener, daemon=True)
    input_thread.start()
    
    # Основной цикл
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
            
    except KeyboardInterrupt:
        print("\n\nСервис остановлен (Ctrl+C)")
    
    print("Сервис завершил работу")






