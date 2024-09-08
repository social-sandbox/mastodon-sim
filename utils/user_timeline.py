# This script loads a list of unique user IDs from a file, fetches account information (username) for each user,
# and retrieves their public statuses (toots). The statuses are stored in a Pandas DataFrame and saved to CSV files,
# with each file named after the corresponding username. The process is repeated for all user IDs listed in the file.
# Pagination is handled by using the 'max_id' parameter, fetching statuses in batches until no more are available.

import json

import pandas as pd
import requests

# Load user IDs from the 'unique_user_ids.txt' file
with open("unique_user_ids.txt") as file:
    user_ids = [line.strip() for line in file.readlines()]

# Loop through each user ID and fetch their statuses
for user_id in user_ids:
    # Fetch the user's account information to get the username
    account_url = f"https://social-sandbox.com/api/v1/accounts/{user_id}"
    account_response = requests.get(account_url)
    account_info = json.loads(account_response.text)
    username = account_info["username"]  # Extract username from the account info

    # Now fetch the statuses for the user
    URL = f"https://social-sandbox.com/api/v1/accounts/{user_id}/statuses"
    params = {
        "limit": 40  # Fetch 40 statuses at a time
    }

    results = []

    # Infinite loop to handle pagination and fetch all statuses
    while True:
        r = requests.get(URL, params=params)
        toots = json.loads(r.text)

        # Break if there are no more toots
        if len(toots) == 0:
            break

        # Process each toot and extract relevant data
        for t in toots:
            toot_data = {
                "id": t["id"],
                "created_at": t["created_at"],
                "content": t["content"],
                "in_reply_to_id": t["in_reply_to_id"],
                "in_reply_to_account_id": t["in_reply_to_account_id"],
                "sensitive": t["sensitive"],
                "mentions": t["mentions"],
            }
            results.append(toot_data)

        # If the number of toots is less than the limit, it means we've reached the last page
        if len(toots) < params["limit"]:
            break

        # Update the 'max_id' to fetch the next set of toots (pagination)
        max_id = toots[-1]["id"]
        params["max_id"] = max_id

    # Convert the results to a Pandas DataFrame
    df = pd.DataFrame(results)

    # Save the DataFrame to a CSV file named after the username
    df.to_csv(f"{username}_statuses.csv", index=False)
    print(f"Saved data for user {username} to {username}_statuses.csv")
