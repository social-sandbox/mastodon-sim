import argparse
import re

import matplotlib.pyplot as plt
import pandas as pd


# Function to parse the score data
def parse_scores(filename):
    data = {"Episode": [], "Judge": [], "ScoredPerson": [], "Score": []}

    episode = None
    with open(filename) as file:
        for line in file:
            line = line.strip()

            # Find episode line
            if line.startswith("Episode"):
                episode = int(line.split(":")[1].strip())
            else:
                # Use regex to parse the scores
                match = re.match(r"(.*) gives (.*) a score of (\d+)", line)
                if match:
                    judge = match.group(1).strip()
                    scored_person = match.group(2).strip()
                    score = int(match.group(3).strip())

                    data["Episode"].append(episode)
                    data["Judge"].append(judge)
                    data["ScoredPerson"].append(scored_person)
                    data["Score"].append(score)

    return pd.DataFrame(data)


# Function to calculate polling average data
def parse_votes(filename):
    data = {"Episode": [], "Voter": [], "VotedFor": []}

    episode = None
    with open(filename) as file:
        for line in file:
            line = line.strip()

            # Find episode line
            if line.startswith("Episode"):
                episode = int(line.split(":")[1].strip())
            else:
                # Use regex to parse the votes
                match = re.match(r"(.*) votes for (.*)", line)
                if match:
                    voter = match.group(1).strip()
                    voted_for = match.group(2).strip()

                    data["Episode"].append(episode)
                    data["Voter"].append(voter)
                    data["VotedFor"].append(voted_for)

    return pd.DataFrame(data)


# Function to calculate vote percentages for polling
def calculate_polling_average(data):
    episodes = sorted(data["Episode"].unique())

    results = {"Episode": [], "Bill": [], "Bradley": []}

    for episode in episodes:
        episode_data = data[data["Episode"] == episode]
        total_votes = len(episode_data)
        bill_votes = len(episode_data[episode_data["VotedFor"] == "Bill"])
        bradley_votes = len(episode_data[episode_data["VotedFor"] == "Bradley"])

        results["Episode"].append(episode)
        results["Bill"].append((bill_votes / total_votes) * 100)
        results["Bradley"].append((bradley_votes / total_votes) * 100)

    return pd.DataFrame(results)


# Function to create the polling average plot
def plot_polling_average(data):
    plt.figure(figsize=(12, 8))

    # Plot Bill's polling average
    plt.plot(
        data["Episode"],
        data["Bill"],
        label="Bill",
        marker="o",
        markersize=8,
        linewidth=3,
        color="#2E86C1",
        alpha=0.85,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    # Plot Bradley's polling average
    plt.plot(
        data["Episode"],
        data["Bradley"],
        label="Bradley",
        marker="o",
        markersize=8,
        linewidth=3,
        color="#E74C3C",
        alpha=0.85,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    # Add titles and labels
    plt.title(
        "Polling Average for Bill and Bradley Over Episodes",
        fontsize=18,
        fontweight="bold",
        pad=20,
        fontfamily="DejaVu Sans",
    )
    plt.xlabel("Episode", fontsize=14, labelpad=10, fontfamily="DejaVu Sans")
    plt.ylabel("Percentage of Votes (%)", fontsize=14, labelpad=10, fontfamily="DejaVu Sans")

    # Customize the grid for a more subtle look
    plt.grid(True, linestyle="--", alpha=0.4, color="#bfbfbf")

    # Customize the ticks and tick labels
    plt.xticks(data["Episode"], fontsize=12, fontfamily="DejaVu Sans")
    plt.yticks(range(0, 101, 10), fontsize=12, fontfamily="DejaVu Sans")

    # Remove top and right borders for a cleaner look
    plt.gca().spines["top"].set_visible(False)
    plt.gca().spines["right"].set_visible(False)

    # Add legend
    plt.legend(loc="upper left", fontsize=12, frameon=False)

    # Final styling touch
    plt.tight_layout()

    # Show the plot
    plt.show()


# Function to create the score plot
def plot_scores(data):
    # Filter data for Bill and Bradley
    bill_data = data[data["ScoredPerson"] == "Bill"].groupby("Episode")["Score"].mean()
    bradley_data = data[data["ScoredPerson"] == "Bradley"].groupby("Episode")["Score"].mean()

    # Create the plot
    plt.figure(figsize=(12, 8))

    # Plot Bill's scores
    plt.plot(
        bill_data.index,
        bill_data.values,
        label="Bill",
        marker="o",
        markersize=8,
        linewidth=3,
        color="#2E86C1",
        alpha=0.85,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    # Plot Bradley's scores
    plt.plot(
        bradley_data.index,
        bradley_data.values,
        label="Bradley",
        marker="o",
        markersize=8,
        linewidth=3,
        color="#E74C3C",
        alpha=0.85,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    # Add titles and labels
    plt.title(
        "Average Scores for Bill and Bradley Over Episodes",
        fontsize=18,
        fontweight="bold",
        pad=20,
        fontfamily="DejaVu Sans",
    )
    plt.xlabel("Episode", fontsize=14, labelpad=10, fontfamily="DejaVu Sans")
    plt.ylabel("Average Score", fontsize=14, labelpad=10, fontfamily="DejaVu Sans")

    # Customize the grid for a more subtle look
    plt.grid(True, linestyle="--", alpha=0.4, color="#bfbfbf")

    # Customize the ticks and tick labels
    plt.xticks(bill_data.index, fontsize=12, fontfamily="DejaVu Sans")
    plt.yticks(range(11), fontsize=12, fontfamily="DejaVu Sans")

    # Remove top and right borders for a cleaner look
    plt.gca().spines["top"].set_visible(False)
    plt.gca().spines["right"].set_visible(False)

    # Add legend
    plt.legend(loc="upper left", fontsize=12, frameon=False)

    # Final styling touch
    plt.tight_layout()

    # Show the plot
    plt.show()


# Function to detect if the file contains voting or scoring data
def detect_file_type(filename):
    with open(filename) as file:
        for line in file:
            if "votes for" in line:
                return "votes"
            if "a score of" in line:
                return "scores"
    return None


# Main function to handle reading, detecting, and plotting
def main(filename):
    # Detect the type of file
    file_type = detect_file_type(filename)

    if file_type == "votes":
        print("Detected polling data")
        vote_data = parse_votes(filename)
        polling_data = calculate_polling_average(vote_data)
        plot_polling_average(polling_data)
    elif file_type == "scores":
        print("Detected scoring data")
        score_data = parse_scores(filename)
        plot_scores(score_data)
    else:
        print("Unrecognized file format")


# Entry point to handle command-line arguments
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process and visualize polling or score data from a file."
    )
    parser.add_argument("filename", type=str, help="The path to the file containing the data.")
    args = parser.parse_args()

    main(args.filename)
