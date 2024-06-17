import pandas as pd
import requests

df = pd.read_excel(r'D:\all_pokemon_data.xlsx')
final_urls = []

for index, row in df.iterrows():
    url = row['Urls']
    condition = row['Condition']
    printing = row['Printing']

    if pd.notnull(url) and pd.notnull(condition) and pd.notnull(printing):
        try:
            response = requests.get(url)
            final_url = response.url

            # Append based on Printing value (Exact match check)
            if printing == 'Holofoil':
                final_url += "&Printing=Holofoil"
            elif printing == 'Normal':
                final_url += "&Printing=Normal"
            elif printing == '1st Edition Holofoil':
                final_url += "&Printing=1st+Edition+Holofoil"
            elif printing == '1st Edition':
                final_url += "&Printing=1st+Edition"
            elif printing == 'Reverse Holofoil':
                final_url += "&Printing=Reverse+Holofoil"

            # Append based on Condition value
            if 'Lightly Played+' in condition:
                final_url += "&ListingType=standard&page=1&Condition=Lightly+Played|Near+Mint"
            elif 'Near Mint' in condition:
                final_url += "&ListingType=standard&page=1&Condition=Near+Mint"
            else:
                final_url += "&ListingType=standard&page=1"  # Default append

            print("Final URL after redirection and appending condition and printing:", final_url)
            final_urls.append(final_url)
            df.at[index, 'New_URL'] = final_url  # Updating the 'New_URL' column in the DataFrame

        except Exception as e:
            print(f"Error processing URL: {url}. Error: {e}")
            continue

    else:
        print("Missing URL, condition, or printing in this row. Skipping...")

# Append final URLs to a new DataFrame
df_final_urls = pd.DataFrame({'Final_URLs': final_urls})
print(df_final_urls)

# Write the updated DataFrame back to the Excel file with the 'New_URL' column
df.to_excel(r'D:\all_pokemon_data.xlsx', index=False)