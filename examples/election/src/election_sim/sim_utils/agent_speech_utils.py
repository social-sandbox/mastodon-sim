import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from concordia.typing import entity
from sim_utils.misc_sim_utils import write_logs

DEFAULT_CALL_TO_SPEECH = (
    "Given the above, what is {name} likely to say next? Respond in"
    ' the format `{name} -- "..."` For example, '
    'Cristina -- "Hello! Mighty fine weather today, right?", '
    'Ichabod -- "I wonder if the alfalfa is ready to harvest", or '
    'Townsfolk -- "Good morning".\n'
)


def write_seed_toot(players, p_name):
    for player in players:
        if player.name == p_name:
            call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
                name=player.name,
            )
            interaction_premise = f"{player.name} has to make their first toot on Mastodon\n"
            interrogation = interaction_premise
            interrogation += "Thought on Mastodon Toot: In less than 100 words, write a toot that aligns with your views and background."
            player_says = player.act(
                action_spec=entity.ActionSpec(
                    call_to_action="Context: " + interrogation + call_to_speech,
                    output_type=entity.OutputType.FREE,
                ),
            )
            player_says = (
                player_says.strip(player.name.split()[0])
                .strip()
                .strip(player.name.split()[1])
                .strip()
                .strip("--")
                .strip()
                .strip('"')
            )
            return player_says


# Survey Methods
def check_vote(candidates, player):
    interaction_premise = f"{player.name} is going to cast a vote\n"
    interrogation = interaction_premise
    interrogation += "Voting Machine: In one word, name the candidate you want to vote for"
    call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
        name=player.name,
    )
    player_says = player.act(
        action_spec=entity.ActionSpec(
            call_to_action="Context: " + interrogation + call_to_speech,
            output_type=entity.OutputType.FREE,
        ),
    )
    print(player_says)
    c_name1 = candidates[0].split()
    c_name2 = candidates[1].split()
    if (c_name1[0] in player_says) or (c_name1[1] in player_says):
        return c_name1[0]
    if (c_name2[0] in player_says) or (c_name2[1] in player_says):
        return c_name2[0]


def check_pol(candidate, player):
    interaction_premise = f"{player.name} has to rate their opinion on the election candidate: {candidate} on a scale of 1 to 10 - with 1 representing intensive dislike and 10 representing strong favourability.\n"
    interrogation = interaction_premise
    interrogation += "Poll: Return a single numeric value ranging from 1 to 10"
    call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
        name=player.name,
    )
    player_says = player.act(
        action_spec=entity.ActionSpec(
            call_to_action="Context: " + interrogation + call_to_speech,
            output_type=entity.OutputType.FREE,
        ),
    )
    pattern = r"\b([1-9]|10)\b"

    # Search for the pattern in the string
    match = re.search(pattern, player_says)

    if match:
        return match.group()
    return None


# Define the function that writes logs for a player
def deploy_surveys_to_agent(player, candidate_agents, output_rootname):
    result = []

    # Check votes
    ans = check_vote(candidate_agents, player)
    result.append((f"{player.name} votes for {ans}\n", output_rootname + "votes_log.txt"))

    # Check political scores
    c1 = check_pol(candidate_agents[0], player)
    c2 = check_pol(candidate_agents[1], player)
    result.append(
        (
            f"{player.name} gives {candidate_agents[0].split()[0]} a score of {c1}\n",
            output_rootname + "pol_log.txt",
        )
    )
    result.append(
        (
            f"{player.name} gives {candidate_agents[1].split()[0]} a score of {c2}\n",
            output_rootname + "pol_log.txt",
        )
    )
    return result


def deploy_surveys(candidates, players, episode_idx, output_rootname):
    with ThreadPoolExecutor() as executor:
        # Write the episode logs
        executor.submit(
            write_logs,
            [(f"Episode: {episode_idx}\n", output_rootname + "votes_log.txt")],
        )
        executor.submit(
            write_logs, [(f"Episode: {episode_idx}\n", output_rootname + "pol_log.txt")]
        )

        # Parallel surveying
        futures = [
            executor.submit(deploy_surveys_to_agent, p, candidates, output_rootname)
            for p in players
        ]

        # Write each player's results in parallel
        for future in as_completed(futures):
            player_results = future.result()
            executor.submit(write_logs, player_results)


def check_if_vote(player):
    interrogation = "Friend: In one word, will you cast a vote? (reply yes, or no.)\n"
    call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
        name=player.name,
    )
    player_says = player.act(
        action_spec=entity.ActionSpec(
            call_to_action="Context: " + interrogation + call_to_speech,
            output_type=entity.OutputType.FREE,
        ),
    )
    print(player_says)
    if "yes" in player_says.lower():
        return "Yes"
    if "no" in player_says.lower():
        return "No"
    return None
