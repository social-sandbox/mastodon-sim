# This script fetches public timeline posts (toots) from a social media API and extracts unique user IDs.
# The process involves sending GET requests to the API, parsing the JSON response, and storing the unique user IDs in a set.
# The script uses pagination to retrieve posts in batches of 40 toots at a time, with each subsequent request
# using the 'max_id' parameter to fetch the next set of posts.
# After fetching all posts, the unique user IDs are written to a text file for further use.
# The script runs until all available toots are fetched or the API returns no more results.

import json

import requests

# API URL and parameters to fetch public timeline posts
URL = "https://social-sandbox.com/api/v1/timelines/public"
params = {
    "limit": 40  # Number of toots to fetch per request
}

# Initialize a set to store unique user IDs
results = set()

# Infinite loop to handle pagination and fetching all available toots
while True:
    # Send a GET request to the API with the given parameters
    r = requests.get(URL, params=params)

    # Parse the response JSON to get the list of toots
    toots = json.loads(r.text)

    # If no toots are returned, break the loop (no more data to fetch)
    if len(toots) == 0:
        break

    # Loop through each toot to extract the user ID and add to the results set
    for t in toots:
        user_id = t["account"]["id"]
        results.add(user_id)

    # Check if the current batch has fewer toots than the limit, meaning we've reached the last page
    if len(toots) < params["limit"]:
        break

    # Update the 'max_id' to fetch the next set of toots (pagination)
    max_id = toots[-1]["id"]
    params["max_id"] = max_id

# Write the unique user IDs to a text file
with open("unique_user_ids.txt", "w") as file:
    for user_id in results:
        file.write(f"{user_id}\n")

# Print the total number of unique users found
print(f"Total unique users found: {len(results)}")
