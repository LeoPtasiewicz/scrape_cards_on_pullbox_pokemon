import pandas as pd
import sqlite3
from os.path import exists

def filter_and_save_to_db(input_file, output_db):
    # Check if the input file exists
    if not exists(input_file):
        raise FileNotFoundError(f"The file {input_file} does not exist.")
    
    try:
        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(input_file)
        
        # Filter the DataFrame to exclude rows where the "value" column is null
        filtered_df = df.dropna(subset=['details'])
        
        # Select only the specified columns
        filtered_df = filtered_df[['name', 'source', 'details', 'value']]
        
        # Use a context manager to handle the SQLite database connection
        with sqlite3.connect(output_db) as conn:
            # Write the filtered data to a new table named 'filtered_data' in the database
            filtered_df.to_sql('filtered_data', conn, if_exists='replace', index=False)
            
        print("Filtered data has been written to", output_db)
    except Exception as e:
        print("An error occurred:", e)

# Example usage
input_file = r"C:\Users\Leo Ptasiewicz\Desktop\data.csv"
output_db = r"C:\Users\Leo Ptasiewicz\Desktop\test4.db"  # Output SQLite database file path on Desktop

filter_and_save_to_db(input_file, output_db)
