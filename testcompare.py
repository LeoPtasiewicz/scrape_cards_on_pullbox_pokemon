import sqlite3
import os
import requests
import json

def fetch_all_card_data(cursor):
    cursor.execute("SELECT name, box_name, price_avg FROM card_data")
    return {row[:2]: row[2] for row in cursor.fetchall()}

def send_discord_messages(webhook_url, data):
    message_content = data["content"]
    max_length = 2000  # Discord's limit for message content length
    parts = []
    
    # Split the message content into parts that fit within Discord's limit
    while len(message_content) > max_length:
        last_newline = message_content[:max_length].rfind('\n')
        if last_newline == -1:
            last_newline = max_length
        parts.append(message_content[:last_newline])
        message_content = message_content[last_newline:].strip()
    parts.append(message_content)  # Add the remaining part

    # Send each part as a separate message
    for part in parts:
        response = requests.post(webhook_url, json={"content": part, "username": data["username"]})
        if response.status_code != 204:
            print(f"Failed to send part of the message, status code: {response.status_code}")

def compare_databases(today_db_path, yesterday_db_path, webhook_url):
    # Connect to today's database and fetch data
    conn_today = sqlite3.connect(today_db_path)
    cursor_today = conn_today.cursor()
    today_data = fetch_all_card_data(cursor_today)
    cursor_today.close()
    conn_today.close()

    # Connect to yesterday's database and fetch data
    conn_yesterday = sqlite3.connect(yesterday_db_path)
    cursor_yesterday = conn_yesterday.cursor()
    yesterday_data = fetch_all_card_data(cursor_yesterday)
    cursor_yesterday.close()
    conn_yesterday.close()

    # Compare the price_avg for each card
    differences = []
    for card in today_data:
        today_price = today_data[card]
        yesterday_price = yesterday_data.get(card)
        if str(today_price) != str(yesterday_price):
            differences.append((card[0], card[1], yesterday_price, today_price))

    # Send the differences via Discord webhook
    if differences:
        message_content = "Differences found in price_avg between today and yesterday:\n"
        for name, box_name, price_yesterday, price_today in differences:
            message_content += f"{name} in {box_name} - Yesterday: {price_yesterday}, Today: {price_today}\n"
        send_discord_messages(webhook_url, {"content": message_content, "username": "Price Checker Bot"})
    else:
        print("No differences found in price_avg between the two databases.")

# Define the paths to the databases and the Discord webhook URL
desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
today_db_path = os.path.join(desktop_path, 'pullbox_cards.db')
yesterday_db_path = os.path.join(desktop_path, 'pullbox_cards_yesterday.db')
webhook_url = 'https://discord.com/api/webhooks/1232752903140278342/uXpkRiAjvN3nw4iCs9t0K42HZZj3x_ddvZ7sAcgHa5CYcCEPGTzQG1TtL8JLu7ZFpnl5'

# Run the comparison
compare_databases(today_db_path, yesterday_db_path, webhook_url)
