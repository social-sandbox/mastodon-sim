# This script retrieves public timelines (toots) from a social sandbox API.
# It sends a GET request to the API and fetches posts in batches with a specified limit.
# The results are stored in a list, converted into a DataFrame, and displayed.
# The script includes pagination logic to fetch all available data by adjusting the 'max_id' in the request parameters.
# Data for each toot includes the ID, creation time, content, whether it's a reply, sensitivity, and mentions.
# The process continues until no more toots are available, i.e., the last batch returns fewer items than the limit.

import json

import pandas as pd
import requests

# Define the API URL and parameters for the request
URL = "https://social-sandbox.com/api/v1/timelines/public"
params = {
    "limit": 40  # Fetch 40 toots per request
}

# Initialize an empty list to store the results
results = []

# Infinite loop to handle pagination and continue fetching data until the end
while True:
    # Make a GET request to the API with the given parameters
    r = requests.get(URL, params=params)

    # Parse the JSON response
    toots = json.loads(r.text)

    # Break the loop if no more toots are returned
    if len(toots) == 0:
        break

    # Process each toot in the current batch
    for t in toots:
        # Extract relevant data from each toot
        toot_data = {
            "id": t["id"],
            "created_at": t["created_at"],
            "content": t["content"],
            "in_reply_to_id": t["in_reply_to_id"],
            "in_reply_to_account_id": t["in_reply_to_account_id"],
            "sensitive": t["sensitive"],
            "mentions": t["mentions"],
        }
        # Append the toot data to the results list
        results.append(toot_data)

    # If the number of toots is less than the limit, we've reached the last batch
    if len(toots) < params["limit"]:
        break

    # Update the 'max_id' parameter to fetch the next set of toots
    max_id = toots[-1]["id"]
    params["max_id"] = max_id

# Convert the results into a pandas DataFrame
df = pd.DataFrame(results)

# Display the DataFrame
print(df)
