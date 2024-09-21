import argparse

from dotenv import find_dotenv, load_dotenv

from mastodon_sim.logging_config import logger
from mastodon_sim.mastodon_ops.get_client import get_client


# Simulate get_user function
def get_user(toot_id):
    load_dotenv(find_dotenv())
    try:
        mastodon = get_client()
        response = mastodon.status(toot_id)
        # print(response["account"]["display_name"])
        return response["account"]["display_name"]
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        return "Error"


# Function to process lines and write to another file
def process_file(input_file_path, output_file_path):
    with open(input_file_path) as infile, open(output_file_path, "w") as outfile:
        for line in infile:
            line = line.strip()
            if "Episode: " in line:
                line = line.strip("Episode: ")
                while line[0].isdigit():
                    line = line[1:]
            if "liked" in line:
                parts = line.split()
                display_name = parts[0]  # Assuming the last word is the toot_id
                outfile.write(f"{parts[0]} liked {display_name}\n")
            # elif 'replied' in line:
            #     parts = line.split()
            #     display_name = get_user(parts[-1])  # Assuming the last word is the toot_id
            #     outfile.write(f"{parts[0]} replied {display_name}\n")
            elif "boosted" in line:
                parts = line.split()
                outfile.write(f"{parts[0]} boosted {parts[5]}\n")
            else:
                outfile.write(line + "\n")


# Example usage
if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run the Dash app with specific data files.")
    parser.add_argument("input_file_path", type=str, help="The path to the app log file.")
    parser.add_argument("output_file_path", type=str, help="The path to the output.")
    args = parser.parse_args()
    process_file(args.input_file_path, args.output_file_path)
