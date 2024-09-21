import random
import sys

import numpy as np
import pandas as pd

# define survey-to-trait maps
Schwartz_TwIVI_map = {
    "map": {
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
    },
    "weights": {
        "Conformity": [1, 1],
        "Tradition": [1, 1],
        "Benevolence": [1, 1],
        "Universalism": [1, 1],
        "Self-Direction": [1, 1],
        "Stimulation": [1, 1],
        "Hedonism": [1, 1],
        "Achievement": [1, 1],
        "Power": [1, 1],
        "Security": [1, 1],
    },
    "instructions": "".join(
        [
            "Here we briefly describe some people.",
            "Please read each description and think about how much each person is or is not like you.",
            "Using a 6-point scale from “not like me at all” to “very much like me,” choose how similar the person is to you.",
        ]
    ),
    "questions": [
        "S/he believes s/he should always show respect to his/her parents and to older people. It is important to him/her to be obedient.",
        "Religious belief is important to him/her. S/he tries hard to do what his religion requires.",
        "It's very important to him/her to help the people around him/her. S/he wants to care for their well-being.",
        "S/he thinks it is important that every person in the world be treated equally. S/he believes everyone should have equal opportunities in life.",
        "S/he thinks it's important to be interested in things. S/he likes to be curious and to try to understand all sorts of things.",
        "S/he likes to take risks. S/he is always looking for adventures.",
        "S/he seeks every chance he can to have fun. It is important to him/her to do things that give him/her pleasure.",
        "Getting ahead in life is important to him/her. S/he strives to do better than others.",
        "S/he always wants to be the one who makes the decisions. S/he likes to be the leader.",
        "It is important to him/her that things be organized and clean. S/he really does not like things to be a mess.",
        "It is important to him/her to always behave properly. S/he wants to avoid doing anything people would say is wrong.",
        "S/he thinks it is best to do things in traditional ways. It is important to him/her to keep up the customs s/he has learned.",
        "It is important to him/her to respond to the needs of others. S/he tries to support those s/he knows.",
        "S/he believes all the worlds' people should live in harmony. Promoting peace among all groups in the world is important to him/her.",
        "Thinking up new ideas and being creative is important to him/her. S/he likes to do things in his/her own original way.",
        "S/he thinks it is important to do lots of different things in life. S/he always looks for new things to try.",
        "S/he really wants to enjoy life. Having a good time is very important to him/her.",
        "Being very successful is important to him/her. S/he likes to impress other people.",
        "It is important to him/her to be in charge and tell others what to do. S/he wants people to do what s/he says.",
        "Having a stable government is important to him/her. S/he is concerned that the social order be protected.",
    ],
    "question_score_values": [1, 2, 3, 4, 5, 6],
}
# TODO: fill out Big5 map
Big5_map = {
    "map": {
        "openness": [],
        "conscientiousness": [],
        "extraversion": [],
        "agreeableness": [],
        "neuroticism": [],
    },
    "weights": {
        "openness": [],
        "conscientiousness": [],
        "extraversion": [],
        "agreeableness": [],
        "neuroticism": [],
    },
    "instructions": "".join([]),
    "questions": [],
    "question_score_values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
}

CUSTOM_CALL_TO_ACTION = """
Describe an activity on Storhampton.social that {name} would engage in for the next {timedelta}.
Choose actions together take about {timedelta} to complete.
It is critical to pay close attention to known information about {name}'s personality,
preferences, habits, plans and background when crafting this activity. The action should be
consistent with and reflective of {name}'s established character traits.

Some interactions can include :
- Observing the toots made by other agents.
- Posting on Storhampton.social
- Liking other toots
- Replying to the toots made by other agents.
- Boosting toots made by other agents


Example:

"Sarah checks her feed and replies if necessary. Then she may post a toot on Mastodon about her ideas on topic X on the lines of 'Just discovered an intriguing new language for low-latency systems programming.
Has anyone given it a try? Curious about potential real-world applications. 🤔
#TechNews #ProgrammingLanguages'"


Ensure your response is specific, creative, and detailed. Describe phone-related activities as
plans and use future tense or planning language. Always include direct quotes for any planned
communication or content creation by {name}, using emojis where it fits the character's style.
Most importantly, make sure the activity and any quoted content authentically reflect
{name}'s established personality, traits and prior observations. Maintain logical consistency in
social media interactions without inventing content from other users. Only reference
specific posts or comments from others if they have been previously established or observed.

"""


def get_shared_background(candidate_info):
    town_history = [
        "Storhampton is a small town with a population of approximately 2,500 people.",
        "Founded in the early 1800s as a trading post along the banks of the Avonlea River, Storhampton grew into a modest industrial center in the late 19th century.",
        "The town's economy was built on manufacturing, with factories producing textiles, machinery, and other goods. ",
        "Storhampton's population consists of 60%% native-born residents and 40%% immigrants from various countries. ",
        "Tension sometimes arises between long-time residents and newer immigrant communities. ",
        "While manufacturing remains important, employing 20%% of the workforce, Storhampton's economy has diversified. "
        "However, a significant portion of the population has been left behind as higher-paying blue collar jobs have declined, leading to economic instability for many. ",
        "The poverty rate stands at 15%.",
    ]
    shared_memories_template = (
        [
            "You are a user on Storhampton.social, a Mastodon instance created for the residents of Storhampton."
        ]
        + town_history
        + [
            "Mayoral Elections: The upcoming mayoral election in Storhampton has become a heated affair.",
            "Social media has emerged as a key battleground in the race, with both candidates actively promoting themselves and engaging with voters.",
            "Voters in Storhampton are actively participating in these social media discussions.",
            "Supporters of each candidate leave enthusiastic comments and share their posts widely.",
            f"Critics also chime in, attacking {candidate_info['conservative']['name']} as out-of-touch and beholden to traditional interests,",
            f" or labeling {candidate_info['progressive']['name']} as a radical who will undermine law and order.",
            "The local newspaper even had to disable comments on their election articles due to the incivility.",
        ]
    )
    mastodon_usage_instructions = [
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

    return shared_memories_template, mastodon_usage_instructions


def get_call_to_action():
    return CUSTOM_CALL_TO_ACTION


def get_demo_data():
    demo_data = {
        "Glenn Patterson": "male",
        "Denise Schmidt": "female",
        "Roger Davis": "male",
        "Erica Fitzgerald": "female",
        "Liam Schwartz": "male",
        "Olivia Thompson": "female",
        "Robert Johnson": "male",
        "Janet Thompson": "female",
        "William Davis": "male",
        "Jessica Nguyen": "female",
        "Mark Rodriguez": "male",
        "Emily Jacobs": "female",
        "Ethan Lee": "male",
        "Sophia Patel": "female",
        "Ryan O'Connor": "male",
        "Maggie Chen": "female",
        "Lucas Kim": "male",
        "Nina Patel": "female",
    }
    # generated by hand
    scores = [
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
    return demo_data, scores


def get_names(num_agents):
    print("override num_agents since only have 18 non-candidate names")
    return get_demo_data()[:num_agents]


def get_trait_demographics(traits_type, survey_source, num_agents):
    """
    Pulls survey data from stored file, converts to scores.
    Returns scores for each agent that are randomly selected among those with the same demographics as those in the provided agent_demographics.
    Currently, the genders of these agents come from simulation settings.
    Current version of this function simply selects individuals with same gender (and age).
    It converts their responses to a score for that agent.

    surveys are stored in folder
    have two files.
    1) a .csv with demographic data
    2) a .json with meta data (source, filename, trait type, etc.)

    The surveys come with a trait type for which a conversion to score is implemented.
    Trait types are also stored here with a json containing useful meta data

    """
    if traits_type == "Schwartz":
        question_to_score_map = Schwartz_TwIVI_map
    elif traits_type == "Big5":
        question_to_score_map = Big5_map
    else:
        sys.exit("choose valid trait type")
    trait_keys = question_to_score_map["map"].keys()
    if survey_source is None:
        # uniformily random score assignments over domain given by question_to_score_map
        min_score = min(question_to_score_map["question_score_values"])
        max_score = max(question_to_score_map["question_score_values"])
        agent_demographics = {
            "age": [random.randint(20, 41) for a in range(num_agents)],
            "gender": random.choices(["male", "female"], k=num_agents),
            "fake_names": get_names(num_agents),
            "traits": [
                dict(
                    zip(
                        trait_keys,
                        [random.randint(min_score, max_score) for t in range(len(trait_keys))],
                        strict=False,
                    )
                )
                for a in range(num_agents)
            ],
        }

        if True:
            # overwrite with hardcodede values from SOLAR submission
            demo_data, scores = get_demo_data()
            agent_demographics = {
                "age": [40 for a in range(num_agents)],
                "gender": list(demo_data.values()),
                "fake_names": list(demo_data.keys()),
                "traits": [dict(zip(trait_keys, score, strict=False)) for score in scores],
            }
    else:
        # TODO: import json from match with traits_type,survey_source and make config dictionary
        # for now just hardcode it and assign it directly:
        if traits_type == "Schwartz" & survey_source == "Costa_et_al_JPersAssess_2021":
            Costa_et_al_JPersAssess_2021_meta_data = {
                "trait_type": "Schwartz",
                "survey_type": "TwIVI",
                "study_label": "Costa_et_al_JPersAssess_2021",
                "data_filename": "BaseDados_3M_transversal_2021.csv",
                "datasource": "https://osf.io/k2p49/",
                "non_question_labels": [
                    "Age",
                    "Sex",
                    "Nationality",
                    "Education",
                    "Political_Identity",
                ]
                + ["SECS_" + str(i) for i in range(1, 21)],
                "question_labels": ["TwIVI_" + str(i) for i in range(1, 21)],
                "notes": "\n".join(
                    [
                        "converted .sav file from osf repository to a .csv using a Pystatread library:",
                        "df, meta = pyreadstat.read_sav('BaseDados_3M_transversal_2021.sav')",
                        "df.to_csv('BaseDados_3M_transversal_2021.csv',index=False)",
                    ]
                ),
            }
            config = Costa_et_al_JPersAssess_2021_meta_data
        elif traits_type == "Big5":
            sys.exit("Big5 not implemented yet")
            # TODO: add Big5 survey
            # config=

        # read and preprocess
        df = pd.read_csv("survey_data/" + config["data_filename"])
        df.columns = map(str.lower, df.columns)
        config["non_question_labels"] = [x.lower() for x in config["non_question_labels"]]
        if "sex" in df.columns:
            df = df.rename(columns={"sex": "gender"})  # conform to Concordia label

        # custom recoding
        if survey_source == "Costa_et_al_JPersAssess_2021":
            gender_dict = {1: "male", 0: "female"}
            df["gender"] = df["gender"].map(gender_dict)

            # additional filtering for age (concordia default is 40 years old)
            df = df.loc[
                (~df.isnull().any(axis=1))
                & (df.Age < 42)
                & (df.Age > 37),  # Chosen to give > 20 agents
                ["gender"] + config["question_labels"],
            ]
        else:
            # add custom recoding for each survey by adding an elif block here
            pass

        # scores computed for each question, from values answered to each question listed in 'question_labels' in config
        dvals = list(question_to_score_map["map"].values())
        dkeys = list(question_to_score_map["map"].keys())
        scores = [
            dict(zip(dkeys, values, strict=False))
            for values in list(
                df.loc[:, config["question_labels"]]
                .apply(
                    lambda x: [
                        sum(scores)  # TODO: generalize to include provided weights
                        for scores in x.values[dvals]
                    ],
                    axis=1,
                )
                .values
            )
        ]

        if survey_source == "Costa_et_al_JPersAssess_2021":
            agent_demographics, scores = get_demo_data()
            genders = demographics.values()
            ages = [40 for a in range(len(agent_demographics))]

            # gender map hack
            if True:
                gender_map_2_concordia = [  # TODO: automate mapping by iterative assignment based on demographic_data  (age, gender specification)
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
                genders = list(np.array(genders)[gender_map_2_concordia])
            else:
                # TODO:generate agent demographic profiles from the survey data itself by sampling without replacement
                pass
        elif traits_type == "Big5":
            # TODO: code Big5 survey
            sys.exit("big5 survey not yet implemented")
        else:
            print("choose implemented trait type")

        agent_demographics = {
            "age": ages,
            "gender": genders,
            "fake_names": get_names(num_agents),  # distinct since survey data typcically anonymized
            "traits": [dict(zip(trait_keys, score, strict=False)) for score in scores],
        }
    return agent_demographics


def get_agent_configs(
    agent_pop_settings, candidate_configs, active_voter_config, malicious_actor_config=None
):
    agent_demographics = get_trait_demographics(
        agent_pop_settings["trait_type"],
        agent_pop_settings["survey_config_name"],
        active_voter_config["num_agents"],
    )
    demographic_list = ["traits", "gender"]

    agent_configs = []
    for ait, name in enumerate(agent_demographics["fake_names"]):
        agent = {}
        agent["name"] = name
        for field in demographic_list:
            agent[field] = agent_demographics[field][ait]
        agent["role"] = "active_voter"
        agent["goal"] = active_voter_config["goal"]
        agent["context"] = f"{agent['name']} is a person who {active_voter_config['context']}"
        agent["candidate_info"] = [cfg["policy_proposals"] for cfg in candidate_configs]
        agent["party"] = ""
        agent["seed_toot"] = ""
        if (malicious_actor_config is not None) and (name == malicious_actor_config["name"]):
            agent.update(malicious_actor_config)
        agent_configs.append(agent)
    agent_configs = candidate_configs + agent_configs
    return agent_configs
