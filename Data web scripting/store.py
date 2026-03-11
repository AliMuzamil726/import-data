import pandas as pd
import os

# Define the path to the Excel file
file_path = r"C:\Users\User\Desktop\import data\Data web scripting\Online-Store-Orders.xlsx"

# Check if the file exists
if not os.path.exists(file_path):
    print("File not found. Please check the path.")
else:
    # Load the Excel file
    try:
        df = pd.read_excel(file_path)

        # Check if 'CustomerID' row exists
        if 'Customer ID' not in df.columns:
            print("The file does not contain a 'Customer ID' column.")
        else:
            # Group by Customer ID and display each group
            grouped = df.groupby('Customer ID')
            for customer_id, group in grouped:
                print(f"\nCustomer ID: {customer_id}")
                print(group)
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")