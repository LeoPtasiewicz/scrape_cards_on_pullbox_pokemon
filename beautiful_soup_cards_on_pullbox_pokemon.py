import requests
from bs4 import BeautifulSoup
import csv

# List of box names
box_names = [
    "1st Edition Base Set Rares!",
    "Maximum VMAX",
    "I Choose You, Charizard!",
    "1st Edition Fossil Rares!",
    "Elite Trainers Only!",
    "1st Edition Jungle Rares!",
    "Tag Team Champions!",
    "The Legendary Beast Hunt",
    "Hidden Fates: Shiny Vault",
    "Master Ball: Psychic Pokemon!",
    "Master Ball: Trainers!",
    "My (Secret) Pokemon!",
    "Tag Team Secrets!",
    "I Choose You, Mew & Mewtwo!",
    "Master Ball: Dark Pokemon!",
    "Welcome to the Gallery!",
    "Legendary Collections!",
    "Legendary Pokemon!",
    "Master Ball: Colorless Pokemon!",
    "Sword and Shield Black Star Promo!",
    "Tag Team Debut!",
    "Master Ball: Water Pokemon!",
    "Master Ball: Fighting Pokemon!",
    "Empowered Trainers!",
    "Collecting Elite Trainer Boxes!",
    "Double Elite Trouble!",
    "Officer Jenny's Secret Stash!",
    "I Choose You, Eevee!",
    "Nurse Joy's Secret Stash!",
    "Master Ball: Lightning Pokemon!",
    "The Earth Badge!",
    "Top Shelf 151",
    "Top Shelf Paradox Rift",
    "My (Secret) Pokemon 2!",
    "Welcome to Galar!",
    "Master Ball: Fire Pokemon!",
    "The Volcano Badge!",
    "I Choose You, Dragonite!",
    "The Marsh Badge!",
    "The Rainbow Badge!",
    "Master Ball: Fairy Pokemon!",
    "Master Ball: Dragon Pokemon!",
    "The Soul Badge!",
    "The Thunder Badge!",
    "The Cascade Badge!",
    "Crown Zenith: Galarian Gallery",
    "Master Ball: Grass Pokemon!",
    "Welcome to Paldea!",
    "Master Ball: Items!",
    "The Boulder Badge!",
    "Gotta Catch 'Em All!",
    "I Choose You, Gengar!",
    "Master Ball: Metal Pokemon!",
    "I Choose You, Pikachu!",
    "Paldean Fates: Shiny Rares!",
    "Pokeball GO! Fire Types+!",
    "Master Ball: 1st Edition Base Set!",
    "Eggcelent Pokemon!",
    "Team Rocket Attacks!",
    "Pokeball GO! Water Types+!",
    "Lost Origin: Trainer Gallery!",
    "Artist Spotlight: Kawayoo!",
    "Master Ball: Stadiums!",
    "Astral Radiance Trainer Gallery!",
    "Brilliant Stars Trainer Gallery!",
    "Pokeball GO! Normal Types+!",
    "Silver Tempest Trainer Gallery!",
    "Artist Spotlight: Tomokazu Komiya",
    "Pokeball GO! Fire Types!",
    "Generations: Radiant Collection!",
    "I Choose You, Tapu!",
    "Pokeball GO! Fighting Types!",
    "Pokeball GO! Fighting Types+!",
    "Celebrations: Classic Collection!",
    "Master Ball: Tools!",
    "Pokeball GO! Normal Types!",
    "Pokeball GO! Flying Types+!",
    "Pokeball GO! Water Types!",
    "I Choose You, Snorlax!",
    "Master Ball: The Gym Leader Challenge!",
    "Artist Spotlight: Ooyama!",
    "Master Ball: 1st Edition Fossil Set!",
    "Master Ball: 1st Edition Jungle Set!",
    "Artist Spotlight: Gemi",
    "I Choose You, Danglers!",
    "Artist Spotlight: Yuka Morii!",
    "Charizard's Spicy Soup",
    "Artist Spotlight: Asako Ito!",
    "Celadon City Soup!",
    "I Can Haz Battle, Meow?"
]

# Function to convert box name to URL
def box_name_to_url(box_name):
    cleaned_name = box_name.lower().replace(" ", "-").replace(",", "").replace("!", "").replace("'", "").replace("?", "").replace("+", "plus")
    return f"https://www.pullbox.gg/box/{cleaned_name}"

# Function to scrape card details from a given URL
def scrape_card_details(url, box_name):
    response = requests.get(url)
    card_data = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        card_containers = soup.find_all("div", class_="whats-in-the-box_card__iD26m")
        
        for container in card_containers:
            card_name_tag = container.find("p", class_="text-center w-full text-xs font-normal line-clamp-2")
            card_name = card_name_tag.text.strip() if card_name_tag else "Unknown Card"

            details = container.find_all("div", class_="flex flex-col items-center justify-center text-center")
            card_details = {"Condition": "", "Printing": "", "Set": ""}
            for detail in details:
                header = detail.find("span", class_="text-xs").text.strip()
                value = detail.find("span", class_="font-normal text-xs").text.strip()
                if header in card_details:
                    card_details[header] = value
            
            card_data.append([card_name, card_details["Condition"], card_details["Printing"], card_details["Set"], box_name])

    return card_data

# CSV file to save the data
csv_file = "card_details3.csv"

# Write to CSV
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["Card Name", "Condition", "Printing", "Set", "Box Name"])
    
    # Iterate through all box names, convert to URL, and scrape card details
    for box_name in box_names:
        url = box_name_to_url(box_name)
        card_details = scrape_card_details(url, box_name)
        
        # Write each card detail to the CSV file
        for card in card_details:
            writer.writerow(card)

print(f"Card details have been saved to {csv_file}")
