from flask import Flask, render_template, request, jsonify, redirect, url_for
from collections import defaultdict
import sqlite3
import re
import os
import urllib.parse
import threading
import requests
from dotenv import load_dotenv
from datetime import datetime
from discord.ext import commands

load_dotenv()
app = Flask(__name__)

def get_db_connection():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'databases', 'pullbox_cards.db')
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at {db_path}")
    print(f"Connecting to database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return redirect(url_for('cards'))

def truncate_label(label):
    return (label[:1000] + '...') if len(label) > 1000 else label

def truncate_number_in_set(number_in_set):
    return (number_in_set[:1000] + '...') if len(number_in_set) > 1000 else number_in_set

@app.route('/cards2')
def cards():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
    SELECT name, label, "set", number_in_set, image_url, price, price_avg, shipping, stock, box_name
    FROM card_data
    ORDER BY box_name, name, label
    ''')
    rows = cur.fetchall()
    
    card_data = defaultdict(lambda: {'prices': [], 'image_url': None, 'number_in_set': None, 'labels': [], 'box_name': None, 'box_class': None})
    previous_box_name = ""
    color_class = "light-blue"
    
    for row in rows:
        card_key = (row['name'], row['box_name'], row['label'])
        card_entry = card_data[card_key]

        card_entry['prices'].append((row['price'], row['stock'], row['shipping']))
        card_entry['price_avg'] = row['price_avg']
        card_entry['image_url'] = row['image_url']
        card_entry['number_in_set'] = truncate_number_in_set(row['number_in_set'])
        
        truncated_label = truncate_label(row['label'])
        if truncated_label not in card_entry['labels']:
            card_entry['labels'].append(truncated_label)
        
        if card_entry['box_name'] is None:
            card_entry['box_name'] = row['box_name']
            if previous_box_name != row['box_name']:
                color_class = "dark-green" if color_class == "light-blue" else "light-blue"
                previous_box_name = row['box_name']
            card_entry['box_class'] = color_class

        # Calculate the new average price
        try:
            card_entry['new_avg_price'] = round(float(row['price_avg']) * 1.679, 2)
        except (TypeError, ValueError):
            card_entry['new_avg_price'] = None

    conn.close()
    
    card_data_str_keys = {f"{key[0]}|||{key[1]}|||{key[2]}": value for key, value in card_data.items()}
    return render_template('cards_pullbox.html', card_data=card_data_str_keys)

@app.route('/hello-world')
def hello_world():
    return 'Hello World!'

def process_name(name):
    processed_name = re.sub(r'\s*\([^)]*\)', '', name)
    return processed_name.strip()

def process_set_name(set_name):
    processed_name = re.sub(r'.*[-:]\s*', '', set_name)
    processed_name = re.sub(r'\s*\([^)]*\)', '', processed_name)
    return processed_name.strip()

def process_card_number(number_in_set):
    processed_number = number_in_set.split('/')[0].lstrip('0')
    return processed_number.strip()

def process_label(label):
    if "1st+Edition+Holofoil" in label:
        return "1st Edition"
    elif "Holofoil" in label and "1st" not in label:
        return "Holofoil"
    elif "1st" in label:
        return "1st Edition"
    return ""

def transform_card_info(name, label, set_name, number_in_set):
    processed_name = process_name(name)
    processed_set_name = process_set_name(set_name)
    processed_card_number = process_card_number(number_in_set)
    special_printing = process_label(label)
    
    final_output = f"{processed_name} #{processed_card_number}"
    if special_printing:
        final_output += f" [{special_printing}]"
    final_output += f" Pokemon {processed_set_name}"

    return final_output

@app.route('/flag_card', methods=['POST'])
def flag_card():
    card_name = request.form['card_name']
    threading.Thread(target=notify_discord, args=(card_name,)).start()
    return jsonify({'status': 'success', 'message': 'Card flagged'})

def notify_discord(card_name):
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("Error: The DISCORD_WEBHOOK_URL is not set in the .env file.")
        return

    message = f"Card {card_name} has been flagged!"
    data = {"content": message}

    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message to Discord: {e}")

@app.route('/card-details')
def card_details():
    card_name_label = request.args.get('name', '')
    try:
        card_name, card_box, card_label = card_name_label.split('|||')
    except ValueError:
        return jsonify(error="Invalid card name, box, and label format."), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT name, label, "set", number_in_set, image_url, price, shipping, stock, url
        FROM card_data
        WHERE name = ? AND box_name = ? AND label = ?
    ''', (card_name, card_box, card_label))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return jsonify(error="Card not found"), 404

    card_data = [{
        'name': row['name'],
        'label': row['label'],
        'set': row['set'],
        'number_in_set': truncate_number_in_set(row['number_in_set']),
        'image_url': row['image_url'],
        'price': row['price'],
        'shipping': row['shipping'],
        'stock': row['stock'],
        'url': row['url']
    } for row in rows]

    return jsonify(card_data=card_data)


@app.route('/submit-ticket', methods=['POST'])
def submit_ticket():
    data = request.get_json()
    username = data.get('username')
    issue = data.get('issue')

    if not username or not issue:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        return jsonify({'status': 'error', 'message': 'Webhook URL not configured'}), 500

    payload = {
        "username": "Ticket Bot",
        "embeds": [{
            "title": "New Ticket Submission",
            "fields": [
                {"name": "Username", "value": username},
                {"name": "Issue", "value": issue}
            ],
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        return jsonify({'status': 'success'})
    except requests.exceptions.RequestException as e:
        print(f"Error submitting ticket: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to submit ticket'}), 500

print("Running the Flask app. Access it at: http://192.168.1.111:5000/cards2")
print("/d/ngrok.exe start my_custom_domain")
if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)