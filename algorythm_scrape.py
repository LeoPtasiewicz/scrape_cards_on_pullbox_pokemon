from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import sympy as sp
import urllib.parse
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import statistics
from bs4 import BeautifulSoup

app = Flask(__name__)

def wait_for_non_empty_text(driver, locator, timeout=10):
    return WebDriverWait(driver, timeout).until(
        lambda d: d.find_element(*locator).text.strip(),
        f"Element with locator {locator} did not have non-empty text after {timeout} seconds"
    )

def get_card_name(driver):
    try:
        card_name = wait_for_non_empty_text(driver, (By.CSS_SELECTOR, 'h1.product-details__name'))
    except TimeoutException:
        card_name = "NA"
    return card_name

def get_listings_info(driver):
    listings_info = []

    try:
        prices = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.listing-item__listing-data__info__price')))
        stocks = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.add-to-cart__available')))
        stocks = stocks[1:]
        sellers = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.listing-item__listing-data__seller .seller-info__name')))
        sales = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.listing-item__listing-data__seller .seller-info__sales')))
        seller_divs = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.listing-item__listing-data__seller')))

        for price, stock, seller, sale, seller_div in zip(prices, stocks, sellers, sales, seller_divs):
            shipping_cost = "0"
            try:
                shipping_cost_element = price.find_element(By.XPATH, "..").find_element(By.CSS_SELECTOR, '.shipping-messages__price')
                shipping_cost = shipping_cost_element.text.strip('+ ').strip(' Shipping').replace('$', '').strip()
            except NoSuchElementException:
                pass

            direct_seller = "no"
            try:
                direct_seller_element = seller_div.find_element(By.CSS_SELECTOR, 'a[title="Direct Seller"]')
                if direct_seller_element:
                    direct_seller = "yes"
            except NoSuchElementException:
                pass

            listings_info.append({
                'Price': price.text.replace('$', '').replace(',', '').strip(),
                'Stock': stock.text.strip(' of'),
                'Shipping Cost': shipping_cost,
                'Seller': seller.text,
                'Sales': sale.text.strip(' ()'),
                'Direct': direct_seller
            })

        if not listings_info:
            listings_info.append({
                'Price': "NA",
                'Stock': "NA",
                'Shipping Cost': "NA",
                'Seller': "NA",
                'Sales': "NA",
                'Direct': "NA"
            })

    except TimeoutException:
        listings_info.append({
            'Price': "NA",
            'Stock': "NA",
            'Shipping Cost': "NA",
            'Seller': "NA",
            'Sales': "NA",
            'Direct': "NA"
        })

    return listings_info

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

def get_listing_info(driver, url):
    listings_data = []
    spotlight_data = {}
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        card_info = get_card_name(driver)
        listings_info = get_listings_info(driver)

        for listing in listings_info:
            listings_data.append({
                'Card Name': card_info,
                'Price': listing['Price'],
                'Stock': listing['Stock'],
                'Shipping Cost': listing['Shipping Cost'],
                'Seller': listing['Seller'],
                'Sales': listing['Sales'],
                'Direct': listing['Direct']
            })

        # Get spotlight info
        spotlight_info = get_spotlight_info(driver)
        spotlight_data = {
            'Card Name': card_info,
            'Spotlight Price': spotlight_info['Spotlight Price'],
            'Spotlight Stock': spotlight_info['Spotlight Stock'],
            'Shipping Cost': "Free Shipping" if spotlight_info['Direct'] == "yes" else "NA",
            'Direct': spotlight_info['Direct']
        }

    except Exception as e:
        print(f"An error occurred with URL {url}: {e}")

    return listings_data, spotlight_data

def initialize_webdriver():
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()))

@app.route('/process-image', methods=['GET'])
def process_image():
    image_url = request.args.get('url')
    if image_url:
        try:
            # Download the image
            response = requests.get(image_url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            
            # Extract image information
            width, height = image.size
            format = image.format

            # Return the information as JSON
            return jsonify({
                "url": image_url,
                "width": width,
                "height": height,
                "format": format
            })
        except requests.RequestException as e:
            return jsonify({"error": "Failed to download image", "details": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "Failed to process image", "details": str(e)}), 400
    else:
        return jsonify({"error": "No image URL provided"}), 400
    
@app.route('/')
def index():
    return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Math API</title>
        </head>
        <body>
            <h1>Enter a mathematical equation</h1>
            <form action="/generate-url" method="get">
                <label for="equation">Equation:</label>
                <input type="text" id="equation" name="eq">
                <input type="submit" value="Generate API URL">
            </form>
            {% if api_url %}
                <h2>Generated API URL:</h2>
                <p><a href="{{ api_url }}" target="_blank">{{ api_url }}</a></p>
            {% endif %}
        </body>
        </html>
    ''')

@app.route('/generate-url', methods=['GET'])
def generate_url():
    equation = request.args.get('eq')
    if equation:
        # Encode the equation for the URL correctly
        encoded_equation = urllib.parse.quote(equation)
        api_url = url_for('calculate', eq=encoded_equation, _external=True)
        return render_template_string('''
            <!doctype html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Math API</title>
            </head>
            <body>
                <h1>Enter a mathematical equation</h1>
                <form action="/generate-url" method="get">
                    <label for="equation">Equation:</label>
                    <input type="text" id="equation" name="eq">
                    <input type="submit" value="Generate API URL">
                </form>
                <h2>Generated API URL:</h2>
                <p><a href="{{ api_url }}" target="_blank">{{ api_url }}</a></p>
            </body>
            </html>
        ''', api_url=api_url)
    else:
        return redirect(url_for('index'))

@app.route('/calculate', methods=['GET'])
def calculate():
    equation = request.args.get('eq')
    if equation:
        try:
            # Log the received equation for debugging
            print(f"Received equation: {equation}")
            
            # Decode the equation from the URL
            equation = urllib.parse.unquote(equation)
            print(f"Decoded equation: {equation}")
            
            # Remove spaces and ensure proper formatting
            equation = equation.replace(" ", "")
            print(f"Processed equation: {equation}")
            
            # Validate and parse the equation
            result = sp.sympify(equation)
            return jsonify({"equation": equation, "result": float(result)})
        except sp.SympifyError as e:
            print(f"SympifyError: {e}")
            return jsonify({"error": "Invalid mathematical expression", "details": str(e)}), 400
        except Exception as e:
            print(f"General Error: {e}")
            return jsonify({"error": "An error occurred", "details": str(e)}), 400
    else:
        return jsonify({"error": "No equation provided"}), 400

@app.route('/process-tcgplayer-url', methods=['GET'])
def process_tcgplayer_url():
    url = request.args.get('url')
    if url:
        driver = initialize_webdriver()
        try:
            listings_data, spotlight_data = get_listing_info(driver, url)
            response_data = {
                "listings": listings_data,
                "spotlight": spotlight_data
            }
            return jsonify(response_data)
        except Exception as e:
            return jsonify({"error": "Failed to process URL", "details": str(e)}), 400
        finally:
            driver.quit()
    else:
        return jsonify({"error": "No URL provided"}), 400

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
