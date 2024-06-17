import sqlite3
import os
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

def wait_for_non_empty_text(driver, locator, timeout=10):
    return WebDriverWait(driver, timeout).until(
        lambda d: d.find_element(*locator).text.strip(),
        f"Element with locator {locator} did not have non-empty text after {timeout} seconds"
    )

def get_card_info(driver):
    try:
        card_name = wait_for_non_empty_text(driver, (By.CSS_SELECTOR, 'h1.product-details__name'))
        card_set = wait_for_non_empty_text(driver, (By.CSS_SELECTOR, 'span[data-testid="lblProductDetailsSetName"]'))
        number_in_set = wait_for_non_empty_text(driver, (By.CSS_SELECTOR, 'span[data-v-b277cce0]'))
    except TimeoutException:
        card_set = "NA"
        number_in_set = "NA"
        try:
            card_name = wait_for_non_empty_text(driver, (By.CSS_SELECTOR, 'h1.product-details__name'))
        except TimeoutException:
            card_name = "NA"

    images = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, 'img')))
    card_image_url = next((img.get_attribute('src') for img in images if 'https://product-images.tcgplayer.com' in img.get_attribute('src')), None)

    return {
        'Card Name': card_name,
        'Card Set': card_set,
        'Number in Set': number_in_set,
        'Image URL': card_image_url
    }

def get_listings_info(driver):
    listings_info = []

    try:
        prices = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.listing-item__listing-data__info__price')))
        stocks = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.add-to-cart__available')))
        stocks = stocks[1:]

        for price, stock in zip(prices, stocks):
            shipping_cost = "NA"
            try:
                shipping_cost_element = price.find_element(By.XPATH, "..").find_element(By.CSS_SELECTOR, '.shipping-messages__price')
                shipping_cost = shipping_cost_element.text.strip('+ ').strip(' Shipping')
            except NoSuchElementException:
                pass

            listings_info.append({
                'Price': price.text,
                'Stock': stock.text.strip(' of'),
                'Shipping Cost': shipping_cost
            })

        if not listings_info:
            listings_info.append({
                'Price': "NA",
                'Stock': "NA",
                'Shipping Cost': "NA"
            })

    except TimeoutException:
        listings_info.append({
            'Price': "NA",
            'Stock': "NA",
            'Shipping Cost': "NA"
        })

    return listings_info

def get_listing_info(driver, url_label_boxname_pairs):
    listings_data = []
    for url, label, box_name in url_label_boxname_pairs:
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            card_info = get_card_info(driver)
            listings_info = get_listings_info(driver)

            price_avg = "NA"
            if listings_info and 'Price' in listings_info[0]:
                prices = [float(listing['Price'].replace('$', '').replace(',', '').strip())
                          for listing in listings_info if listing['Price'] != "NA"]
                if prices:
                    price_avg = sum(prices) / len(prices)
                price_avg = f"{price_avg:.2f}" if prices else "NA"

            for listing in listings_info:
                listing_price = listing['Price'] if listing['Price'] != "NA" else "NA"
                listings_data.append((
                    card_info['Card Name'],
                    label,
                    card_info['Card Set'],
                    card_info['Number in Set'],
                    card_info['Image URL'],
                    box_name,
                    url,
                    listing_price,
                    listing['Shipping Cost'],
                    listing['Stock'],
                    price_avg
                ))

        except Exception as e:
            print(f"An error occurred with URL {url} and label {label}: {e}")
            continue

    return listings_data

def fetch_all_card_data(cursor):
    cursor.execute("SELECT name, box_name, price_avg FROM card_data")
    return {row[:2]: row[2] for row in cursor.fetchall()}

def send_discord_messages(webhook_url, data):
    message_content = data["content"]
    max_length = 2000
    parts = []

    while len(message_content) > max_length:
        last_newline = message_content[:max_length].rfind('\n')
        if last_newline == -1:
            last_newline = max_length
        parts.append(message_content[:last_newline])
        message_content = message_content[last_newline:].strip()
    parts.append(message_content)

    for part in parts:
        response = requests.post(webhook_url, json={"content": part, "username": data["username"]})
        if response.status_code != 204:
            print(f"Failed to send part of the message, status code: {response.status_code}")

def compare_databases(today_db_path, yesterday_db_path, webhook_url):
    conn_today = sqlite3.connect(today_db_path)
    cursor_today = conn_today.cursor()
    today_data = fetch_all_card_data(cursor_today)
    cursor_today.close()
    conn_today.close()

    conn_yesterday = sqlite3.connect(yesterday_db_path)
    cursor_yesterday = conn_yesterday.cursor()
    yesterday_data = fetch_all_card_data(cursor_yesterday)
    cursor_yesterday.close()
    conn_yesterday.close()

    differences = []
    for card in today_data:
        today_price = today_data[card]
        yesterday_price = yesterday_data.get(card)
        if str(today_price) != str(yesterday_price):
            differences.append((card[0], card[1], yesterday_price, today_price))

    if differences:
        message_content = "Differences found in price_avg between today and yesterday:\n"
        for name, box_name, price_yesterday, price_today in differences:
            message_content += f"{name} in {box_name} - Yesterday: {price_yesterday}, Today: {price_today}\n"
        send_discord_messages(webhook_url, {"content": message_content, "username": "Price Checker Bot"})
    else:
        print("No differences found in price_avg between the two databases.")

def initialize_webdriver():
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()))

if __name__ == "__main__":
    db_path = 'c:/users/Leo Ptasiewicz/desktop/cards_on_pullbox.db'
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute('SELECT final_label, label, box_name FROM cards_with_label')
    url_label_boxname_pairs = cursor.fetchall()

    cursor.close()
    connection.close()

    desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    db_path = os.path.join(desktop_path, 'pullbox_cards.db')

    if os.path.exists(db_path):
        today = datetime.today().strftime('%Y-%m-%d')
        new_db_path = os.path.join(desktop_path, 'pullbox_cards_yesterday.db')

        if os.path.exists(new_db_path):
            os.remove(new_db_path)

        os.rename(db_path, new_db_path)

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS card_data (
        name TEXT,
        label TEXT,
        "set" TEXT,
        number_in_set TEXT,
        image_url TEXT,
        box_name TEXT,
        url TEXT,
        price TEXT,
        shipping TEXT,
        stock TEXT,
        price_avg REAL 
    )
    ''')

    num_workers = 4  # Number of Chrome instances to run in parallel
    chunks = [url_label_boxname_pairs[i::num_workers] for i in range(num_workers)]

    drivers = [initialize_webdriver() for _ in range(num_workers)]

    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for driver, chunk in zip(drivers, chunks):
                futures.append(executor.submit(get_listing_info, driver, chunk))

            for future in as_completed(futures):
                listings_data = future.result()
                for data in listings_data:
                    cursor.execute('''
                    INSERT INTO card_data (name, label, "set", number_in_set, image_url, box_name, url, price, shipping, stock, price_avg)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', data)
                connection.commit()
    except KeyboardInterrupt:
        print("Program interrupted by user. Closing resources...")
    finally:
        for driver in drivers:
            driver.quit()
        cursor.close()
        connection.close()

    today_db_path = os.path.join(desktop_path, 'pullbox_cards.db')
    yesterday_db_path = os.path.join(desktop_path, 'pullbox_cards_yesterday.db')
    webhook_url = 'https://discord.com/api/webhooks/1232752903140278342/uXpkRiAjvN3nw4iCs9t0K42HZZj3x_ddvZ7sAcgHa5CYcCEPGTzQG1TtL8JLu7ZFpnl5'

    compare_databases(today_db_path, yesterday_db_path, webhook_url)
