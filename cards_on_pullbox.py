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
import statistics

def get_spotlight_price(driver):
    try:
        price_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.spotlight__price')))
        price = price_element.text.strip().replace('$', '').replace(',', '').strip()
    except TimeoutException:
        price = "NA"
    return price

def get_spotlight_stock(driver):
    try:
        stock_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.add-to-cart__available')))
        stock = stock_element.text.strip().split()[-1]
    except TimeoutException:
        stock = "NA"
    return stock

def is_spotlight_direct(driver):
    direct_seller = "no"
    try:
        driver.find_element(By.CSS_SELECTOR, '.spotlight__banner.direct')
        direct_seller = "yes"
    except NoSuchElementException:
        pass
    return direct_seller

def get_spotlight_info(driver):
    spotlight_info = {}
    try:
        spotlight_price = get_spotlight_price(driver)
        spotlight_stock = get_spotlight_stock(driver)
        direct_seller = is_spotlight_direct(driver)

        spotlight_info = {
            'Spotlight Price': spotlight_price,
            'Spotlight Stock': spotlight_stock,
            'Direct': direct_seller
        }

    except Exception as e:
        print(f"An error occurred: {e}")
        spotlight_info = {
            'Spotlight Price': "NA",
            'Spotlight Stock': "NA",
            'Direct': "NA"
        }

    return spotlight_info

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
    card_image_url = next((img.get_attribute('src') for img in images if 'https://tcgplayer-cdn.tcgplayer.com' in img.get_attribute('src')), None)

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
    spotlight_infos = {}
    card_prices = {}

    for url, label, box_name in url_label_boxname_pairs:
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            card_info = get_card_info(driver)
            listings_info = get_listings_info(driver)

            # Ensure the card name is in the card_prices dictionary
            if card_info['Card Name'] not in card_prices:
                card_prices[card_info['Card Name']] = []

            # Collect prices including shipping costs
            prices_without_shipping = []
            for listing in listings_info:
                price = listing['Price']
                if price != "NA":
                    try:
                        total_price = float(price.replace('$', '').replace(',', '').strip())
                        prices_without_shipping.append(total_price)
                        card_prices[card_info['Card Name']].append(total_price)
                    except ValueError:
                        pass
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
                    "NA"  # Placeholder for price_avg, will be updated later
                ))

            # Get spotlight info
            spotlight_info = get_spotlight_info(driver)
            spotlight_data = (
                card_info['Card Name'],
                spotlight_info['Spotlight Price'],
                spotlight_info['Spotlight Stock'],
                "Free Shipping" if spotlight_info['Direct'] == "yes" else "NA",
                spotlight_info['Direct']
            )
            spotlight_infos[spotlight_data[0]] = spotlight_data

        except Exception as e:
            print(f"An error occurred with URL {url} and label {label}: {e}")
            continue

    # Calculate box price idea
    for card_name, spotlight_data in spotlight_infos.items():
        spotlight_price = spotlight_data[1]
        spotlight_stock = spotlight_data[2]
        spotlight_direct = spotlight_data[4]

        if spotlight_direct == "yes" and spotlight_stock != "NA" and int(spotlight_stock) >= 25:
            # Calculate the average and standard deviation of the first 10 listings
            first_10_prices = [price for price in card_prices[card_name][:10]]
            if len(first_10_prices) > 1:
                avg_first_10 = statistics.mean(first_10_prices)
                std_dev_first_10 = statistics.stdev(first_10_prices)

                if abs(float(spotlight_price) - avg_first_10) <= 2 * std_dev_first_10:
                    box_price = float(spotlight_price)
                else:
                    box_price = statistics.mean(card_prices[card_name])
            else:
                box_price = statistics.mean(first_10_prices) if first_10_prices else "NA"
        else:
            # Calculate the weighted average excluding vendors with fewer than 500 sales and prices outside 2 standard deviations
            if len(card_prices[card_name]) > 1:
                filtered_prices = [price for price in card_prices[card_name] if abs(price - statistics.mean(card_prices[card_name])) <= 2 * statistics.stdev(card_prices[card_name])]
                filtered_prices = [price for price in filtered_prices if any(listing[4] == card_name and int(listing[5].replace(' Sales', '')) >= 500 for listing in listings_data)]
                box_price = statistics.mean(filtered_prices) if filtered_prices else statistics.mean(card_prices[card_name])
            else:
                box_price = statistics.mean(card_prices[card_name]) if card_prices[card_name] else "NA"

        price_avg = f"{box_price:.2f}" if box_price != "NA" else "NA"

        # Update listings_data with the calculated price_avg
        for i in range(len(listings_data)):
            if listings_data[i][0] == card_name:
                listings_data[i] = listings_data[i][:-1] + (price_avg,)

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
    # Define the path to the databases folder in the same directory as the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(script_dir, 'databases')
    
    db_path = os.path.join(base_path, 'cards_on_pullbox_tim.db')
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute('SELECT final_label, label, box_name FROM cards_with_label')
    url_label_boxname_pairs = cursor.fetchall()

    cursor.close()
    connection.close()

    today_db_path = os.path.join(base_path, 'pullbox_cards.db')

    if os.path.exists(today_db_path):
        new_db_path = os.path.join(base_path, 'pullbox_cards_yesterday.db')

        if os.path.exists(new_db_path):
            os.remove(new_db_path)

        os.rename(today_db_path, new_db_path)

    connection = sqlite3.connect(today_db_path)
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

    yesterday_db_path = os.path.join(base_path, 'pullbox_cards_yesterday.db')
    webhook_url = 'https://discord.com/api/webhooks/1232752903140278342/uXpkRiAjvN3nw4iCs9t0K42HZZj3x_ddvZ7sAcgHa5CYcCEPGTzQG1TtL8JLu7ZFpnl5'

    compare_databases(today_db_path, yesterday_db_path, webhook_url)
