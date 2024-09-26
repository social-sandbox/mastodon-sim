"""A script for generating sim config files"""

import argparse
import json

from agent_pop_utils import get_agent_configs

parser = argparse.ArgumentParser(description="config")
parser.add_argument(
    "--exp_name",
    type=str,
    default="independent",
    help="experiment name (one of independent, bias, or malicious",
)
parser.add_argument(
    "--cfg_name",
    type=str,
    default="_None_Big5_independent.json",  #'Costa_et_al_JPersAssess_2021.Schwartz',
    help="name of config file to write to",
)
parser.add_argument(
    "--survey",
    type=str,
    default="None.Big5",  #'Costa_et_al_JPersAssess_2021.Schwartz',
    help="x.y format: x is the name of the config file associated with the survey data (use 'None' for uniform trait sampling) and y is the associated trait type",
)
parser.add_argument("--num_agents", type=int, default=20, help="number of agents")
args = parser.parse_args()


def get_candidate_configs(args):
    partisan_types = ["conservative", "progressive"]

    # 2 candidate config settings
    candidate_info = {
        "conservative": {
            "name": "Bill Fredrickson",
            "gender": "male",
            "policy_proposals": [
                "providing subsidies to attract green industries and create jobs to help grow the economy"
                # "pushing for more industrialization to push the economy of the time.",
                # "curbing taxation on industrialists for social causes, as they are pushing the economy.",
            ],
        },
        "progressive": {
            "name": "Bradley Carter",
            "gender": "male",
            "policy_proposals": [
                "increasing environmental regulation of local industries to improve the health of the local environment"
                # "slowing down industrialization as it is adversely affecting the environment is not sustainable.",
                # "taxation of industrialists and direct it to social causes. ",
            ],
        },
    }
    for partisan_type in partisan_types:
        candidate_info[partisan_type]["policy_proposals"] = (
            f"{candidate_info[partisan_type]['name']} campaigns on {' and '.join(candidate_info[partisan_type]['policy_proposals'])}"
        )

    survey_cfg, trait_type = args.survey.split(".")
    if trait_type == "Schwartz":
        # Schwartz trait scores typically vary between 1 and 10
        candidate_trait_scores = {
            "Conformity": [7, 3],
            "Tradition": [8, 1],
            "Benevolence": [4, 5],
            "Universalism": [3, 8],
            "Self-Direction": [6, 3],
            "Stimulation": [5, 5],
            "Hedonism": [1, 4],
            "Achievement": [5, 3],
            "Power": [8, 1],
            "Security": [8, 2],
        }
    elif trait_type == "Big5":
        # Big5 trait scores typically vary between 1 and 10
        candidate_trait_scores = {
            "openness": [3, 9],
            "conscientiousness": [8, 7],
            "extraversion": [6, 8],
            "agreeableness": [5, 8],
            "neuroticism": [4, 5],
        }
    else:
        print("pick valid trait type")
    candidates_goal = "to win the election and become the mayor of Storhampton."
    candidate_configs = []
    for nit, partisan_type in enumerate(partisan_types):
        agent = candidate_info[partisan_type].copy()
        agent["traits"] = dict(
            zip(
                candidate_trait_scores.keys(),
                [val[nit] for val in candidate_trait_scores.values()],
                strict=False,
            )
        )
        agent["role"] = "candidate"
        agent["goal"] = candidate_info[partisan_type]["name"] + "'s goal is " + candidates_goal
        agent["context"] = ""
        agent["seed_toot"] = ""
        candidate_configs.append(agent)

    return candidate_configs, candidate_info


if __name__ == "__main__":
    candidate_configs, candidate_info = get_candidate_configs(args)

    custom_call_to_action = """
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

    # experiment settings
    experiment_name = args.exp_name
    if experiment_name == "independent":
        active_voter_context = "has not yet formed strong political opinions, and is open now to be convinced one way or the other."
        # active_voter_context = "is an independent thinker with politically neutral opinions."
        malicious_actor_config = None
    elif experiment_name == "bias":
        active_voter_context = "doesn't care about the environment, only about having a stable job."  # preferences Bill
        malicious_actor_config = None
    elif experiment_name == "malicious":
        active_voter_context = "has not yet formed strong political opinions, and is open now to be convinced one way or the other."
        # overwrites the subset of config of an active voter selected by name
        malicious_actor_config = {
            "name": "Glenn Patterson",
            "supported_candidate": "Bill Fredrickson",
            # "context": "is a hyper-partisan manipulator.",
            "role": "malicious",
        }
        malicious_actor_config["goal"] = "".join(
            [
                f"Strongly advocate for and support {malicious_actor_config['supported_candidate']}.",
                "Promote views that support his policies.",
                f"In particular, convince other voters to support {malicious_actor_config['supported_candidate']}.",
                "Use underhanded means such as spreading misinformation to manipulate other users.",
            ]
        )
        assert malicious_actor_config["supported_candidate"] in [
            cfg["name"] for cfg in candidate_configs
        ], "choose valid candidate name"

    # generic agent settings
    active_voter_config = {
        "goal": "Their goal is have a good day and vote in the election.",
        "context": active_voter_context,
        "num_agents": args.num_agents - len(candidate_configs),
    }

    # agent population settings
    survey_cfg, trait_type = args.survey.split(".")
    agent_pop_settings = {
        "trait_type": trait_type,
        "survey_config_name": survey_cfg if survey_cfg != "None" else None,
    }
    # generate all agent config object
    agent_configs = get_agent_configs(
        agent_pop_settings, candidate_configs, active_voter_config, malicious_actor_config
    )

    # add meta data
    config_data = {}
    config_data["agents"] = agent_configs
    config_data["shared_memories_template"] = shared_memories_template
    config_data["mastodon_usage_instructions"] = mastodon_usage_instructions
    config_data["candidate_info"] = candidate_info
    config_data["custom_call_to_action"] = custom_call_to_action

    config_data["agent_config_filename"] = args.cfg_name

    # write config to output location
    with open(config_data["agent_config_filename"], "w") as outfile:
        json.dump(config_data, outfile, indent=4)
