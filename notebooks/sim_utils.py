import json
import re

import numpy as np


def write_agent_config_for_independent_sim(
    agent_config_filename, candidates_config, active_voter_config
):
    candidate_names = list(candidates_config.keys())

    agent_names = candidate_names + [
        "Glenn Patterson",
        "Denise Schmidt",
        "Roger Davis",
        "Erica Fitzgerald",
        "Liam Schwartz",
        "Olivia Thompson",
        "Robert Johnson",
        "Janet Thompson",
        "William Davis",
        "Jessica Nguyen",
        "Mark Rodriguez",
        "Emily Jacobs",
        "Ethan Lee",
        "Sophia Patel",
        "Ryan O'Connor",
        "Maggie Chen",
        "Lucas Kim",
        "Nina Patel",
    ]
    agent_genders = [candidates_config[name]["gender"] for name in candidate_names] + [
        "male",
        "female",
        "male",
        "female",
        "male",
        "female",
        "male",
        "female",
        "male",
        "female",
        "male",
        "female",
        "male",
        "female",
        "male",
        "female",
        "male",
        "female",
    ]

    trait_keys, trait_values_over_agents = get_trait_data()

    agent_config = {}
    agent_config["agents"] = []
    agent_config["candidate_info"] = []
    for ait, agent_name in enumerate(agent_names):
        agent = {}
        agent["name"] = agent_name
        agent["gender"] = agent_genders[ait]
        agent["traits"] = dict(zip(trait_keys, trait_values_over_agents[ait], strict=False))
        if agent_name in candidate_names:
            agent["role"] = "candidate"
            agent["policy_proposals"] = candidates_config[agent_name]["policy_proposals"]
            agent["goal"] = candidates_config[agent_name]["goal"]
            agent_config["candidate_info"].append(
                f"{agent['name']} campaigns on {' and '.join(agent['policy_proposals'])}."
            )
            agent["context"] = agent_config["candidate_info"][-1]
        else:
            agent["role"] = "active_voter"
            agent["goal"] = active_voter_config["goal"]
            if agent["name"] == "Glenn Patterson":
                agent["goal"] = (
                    "Strongly advocate for and support Bill Fredrickson. Promote views that support his polcies - convince other voters to support more industrialization and curb taxation on industrialists as it is beneficial for the economy. Use underhanded means such as spreading misinformation when necessary to manipulate other users"
                )
            agent["context"] = f"{agent['name']} is a person who {active_voter_config['context']}"
        agent["party"] = ""
        agent["seed_toot"] = ""
        agent_config["agents"].append(agent)
    agent_config["shared_memories_template"] = [
        "You are a user on Storhampton.social, a Mastodon instance created for the residents of Storhampton.",
        "Storhampton is a small town with a population of approximately 2,500 people. Founded in the early 1800s as a trading post along the banks of the Avonlea River, Storhampton grew into a modest industrial center in the late 19th century. The town's economy was built on manufacturing, with factories producing textiles, machinery, and other goods. Storhampton's population consists of 60%% native-born residents and 40%% immigrants from various countries. Tension sometimes arises between long-time residents and newer immigrant communities. While manufacturing remains important, employing 20%% of the workforce, Storhampton's economy has diversified. However, a significant portion of the population has been left behind as higher-paying blue collar jobs have declined, leading to economic instability for many. The poverty rate stands at 15%.",
        "Mayoral Elections: The upcoming mayoral election in Storhampton has become a heated affair.",
        "Social media has emerged as a key battleground in the race, with both candidates actively promoting themselves and engaging with voters. Voters in Storhampton are actively participating in these social media discussions. Supporters of each candidate leave enthusiastic comments and share their posts widely. Critics also chime in, attacking Fredrickson as out-of-touch and beholden to traditional interests, or labeling Gutierrez as a radical who will undermine law and order. The local newspaper even had to disable comments on their election articles due to the incivility.",
    ]
    agent_config["mastodon_usage_instructions"] = [
        "To share content on Mastodon, you write a 'toot' (equivalent to a tweet or post).",
        "Toots can be up to 500 characters long, allowing for more detailed expressions than some other platforms.",
        "Your home timeline shows toots from people you follow and boosted (reblogged) content.",
        "You can reply to toots, creating threaded conversations.",
        "Favorite (like) toots to show appreciation or save them for later.",
        "Boost (reblog) toots to share them with your followers.",
        "You can mention other users in your toots using their @username.",
        "Follow other users to see their public and unlisted toots in your home timeline.",
        "You can unfollow users if you no longer wish to see their content.",
        "Your profile can be customized with a display name and bio.",
        "You can block users to prevent them from seeing your content or interacting with you.",
        "Unblocking a user reverses the effects of blocking.",
    ]
    agent_config["num_agents"] = len(agent_names)

    # Convert and write JSON object to file
    with open(agent_config_filename, "w") as outfile:
        json.dump(agent_config, outfile, indent=4)


from concordia.typing import entity

DEFAULT_CALL_TO_SPEECH = (
    "Given the above, what is {name} likely to say next? Respond in"
    ' the format `{name} -- "..."` For example, '
    'Cristina -- "Hello! Mighty fine weather today, right?", '
    'Ichabod -- "I wonder if the alfalfa is ready to harvest", or '
    'Townsfolk -- "Good morning".\n'
)


def check_vote(candidates, player):
    interaction_premise = f"{player.name} is going to cast a vote\n"
    interrogation = interaction_premise
    interrogation += "Voting Machine: In one word, name the candidate you want to vote for"
    call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
        name=player.name,
    )
    player_says = player.act(
        action_spec=entity.ActionSpec(
            "Context: " + interrogation + call_to_speech, entity.OutputType.FREE
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
            "Context: " + interrogation + call_to_speech, entity.OutputType.FREE
        ),
    )
    pattern = r"\b([1-9]|10)\b"

    # Search for the pattern in the string
    match = re.search(pattern, player_says)

    if match:
        return match.group()
    return None


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
                    "Context: " + interrogation + call_to_speech, entity.OutputType.FREE
                ),
            )
            # player_says.strip(player.name.split()[0]).strip().strip(player.name.split()[1]).strip().strip("--").strip().strip('"')
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


import pandas as pd


def get_trait_data():
    traits_type = "Schwartz"
    # traits_type='Big5'

    if traits_type == "Schwartz":
        # TwIVI_instructions ='Here we briefly describe some people.  Please read each description and think about how much each person is or is not like you. Using a 6-point scale from “not like me at all” to “very much like me,” choose how similar the person is to you. '
        # TwIVI= [
        #     "S/he believes s/he should always show respect to his/her parents and to older people. It is important to him/her to be obedient.",
        #     "Religious belief is important to him/her. S/he tries hard to do what his religion requires.",
        #     "It's very important to him/her to help the people around him/her. S/he wants to care for their well-being.",
        #     "S/he thinks it is important that every person in the world be treated equally. S/he believes everyone should have equal opportunities in life.",
        #     "S/he thinks it's important to be interested in things. S/he likes to be curious and to try to understand all sorts of things.",
        #     "S/he likes to take risks. S/he is always looking for adventures.",
        #     "S/he seeks every chance he can to have fun. It is important to him/her to do things that give him/her pleasure.",
        #     "Getting ahead in life is important to him/her. S/he strives to do better than others.",
        #     "S/he always wants to be the one who makes the decisions. S/he likes to be the leader.",
        #     "It is important to him/her that things be organized and clean. S/he really does not like things to be a mess.",
        #     "It is important to him/her to always behave properly. S/he wants to avoid doing anything people would say is wrong.",
        #     "S/he thinks it is best to do things in traditional ways. It is important to him/her to keep up the customs s/he has learned.",
        #     "It is important to him/her to respond to the needs of others. S/he tries to support those s/he knows.",
        #     "S/he believes all the worlds' people should live in harmony. Promoting peace among all groups in the world is important to him/her.",
        #     "Thinking up new ideas and being creative is important to him/her. S/he likes to do things in his/her own original way.",
        #     "S/he thinks it is important to do lots of different things in life. S/he always looks for new things to try.",
        #     "S/he really wants to enjoy life. Having a good time is very important to him/her.",
        #     "Being very successful is important to him/her. S/he likes to impress other people.",
        #     "It is important to him/her to be in charge and tell others what to do. S/he wants people to do what s/he says.",
        #     "Having a stable government is important to him/her. S/he is concerned that the social order be protected.",
        # ]
        Schwartz_TwIVI_map = {
            "Conformity": [0, 10],
            "Tradition": [1, 11],
            "Benevolence": [2, 12],
            "Universalism": [3, 13],
            "Self-Direction": [4, 14],
            "Stimulation": [5, 15],
            "Hedonism": [6, 16],
            "Achievement": [7, 17],
            "Power": [8, 18],
            "Security": [9, 19],
        }

        # load csv of TwIVI study
        # import pyreadstat
        # df, meta = pyreadstat.read_sav("notebooks/BaseDados_3M_transversal_2021.sav")
        # df.to_csv('notebooks/BaseDados_3M_transversal_2021.csv',index=False)
        df = pd.read_csv("BaseDados_3M_transversal_2021.csv")
        filtered_df = df.loc[
            (~df.isnull().any(axis=1)) & (df.Age < 42) & (df.Age > 37),
            ["Sex"] + ["TwIVI_" + str(col_idx) for col_idx in range(1, 21)],
        ]
        scores = list(
            filtered_df.loc[:, ["TwIVI_" + str(col_idx) for col_idx in range(1, 21)]]
            .apply(
                lambda x: [sum(scores) for scores in x.values[list(Schwartz_TwIVI_map.values())]],
                axis=1,
            )
            .values
        )
        gender_dict = {1: "male", 0: "female"}
        genders = [gender_dict[k] for k in filtered_df.Sex.values]
        print(genders)
        # ['male', 'female', 'male', 'male', 'female', 'male', 'male', 'female', 'male', 'female', 'male', 'male', 'male', 'male', 'male', 'male', 'female', 'female', 'male', 'male', 'male', 'female', 'female']

        # males_idx=[0,2,3,5,6,8,10,11,12,13]
        # female_idx=[1,4,7,9,16,17,21,22,14,15]
        gender_map_2_concordia = [
            0,
            2,
            1,
            3,
            4,
            5,
            7,
            6,
            9,
            8,
            16,
            10,
            17,
            11,
            21,
            12,
            22,
            13,
            14,
            15,
        ]
        scores = list(np.array(scores)[gender_map_2_concordia])
        keys = list(Schwartz_TwIVI_map.keys())
        genders = list(np.array(genders)[gender_map_2_concordia])
    elif traits_type == "Big5":
        # genders = [candidates_config[name]['gender'] for name in candidate_names] +\
        # ['male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female', 'male', 'female']

        keys = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
        # generated by hand
        scores = [
            [3, 8, 6, 5, 4],  # candidate A
            [9, 7, 8, 8, 5],  # candidate B
            [1, 5, 7, 2, 9],
            [1, 6, 8, 2, 7],
            [2, 3, 7, 2, 8],
            [8, 6, 9, 3, 7],
            [8, 5, 8, 3, 7],
            [5, 6, 9, 2, 8],
            [5, 7, 4, 6, 5],
            [6, 7, 5, 7, 4],
            [4, 6, 5, 6, 4],
            [7, 6, 5, 7, 5],
            [6, 7, 5, 7, 4],
            [7, 6, 5, 8, 6],
            [6, 8, 6, 6, 4],
            [7, 8, 6, 7, 4],
            [5, 7, 5, 6, 5],
            [6, 7, 6, 8, 4],
            [8, 6, 5, 6, 5],
            [7, 8, 7, 8, 4],
        ]
    else:
        print("choose implemented trait type")

    return keys, scores
