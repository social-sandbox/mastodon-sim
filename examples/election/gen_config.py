"""A script for generating sim config files"""

import argparse
import datetime
import json
from pathlib import Path
from typing import Any

# general instructions
CUSTOM_CALL_TO_ACTION = """
{name} will open the Storhampton.social Mastodon app to engage with other Storhampton residents on the platform for the next {timedelta}, starting by checking their home timeline.

Describe the kinds of social media engagement {name} receives and how they engage with the content of other users within this time period, in particular what social media actions they take.
Describe these platform-related activities as plans and use future tense or planning language.
Be specific, creative, and detailed in your description.
Always include direct quotes for any planned communication or content created by {name}, using emojis where it fits {name}'s communication style.
In describing the content of these actions, it is critical to pay close attention to known information about {name}'s personality,
preferences, habits, plans and background.
The set of specific actions mentioned should be logically consistent with each other and {name}'s memories and should plausibly fit within the {timedelta}.
Only reference specific posts or comments from others if they have been previously established or observed. Do not invent content of other users.

Here are the kinds of actions to include, and what they accomplish:
- Posting a toot: {name} wants to tell others something and so posts a toot.
- Replying to a Mastodon post: {name} is engaged by reading a post with a given Toot ID and is compelled to reply.
- Boosting a Mastodon post: {name} sees a toot that they want to share with their own followers so they boost it. (Return Toot ID and the exact contents of the toot to be boosted.)
- Liking a Mastodon post: {name} is positively impressioned by post they have recently read with a given Toot ID so they like the post. (Return toot ID of the post you want to like)

Here's an example description for a hypothetical Storhampton resident, specifically a programmer named Sarah:

"Sarah will check her home timeline on Storhampton.social and plans to engage posts about the upcoming election.
Then she will post the following toot reflecting what she has observed in light of her interests:
'Has anyone heard anything from the candidates about teaching technology to kids in our community?
I just think this is such an important issue for us. The next generation of Storhamptons needs employable skills!
Curious what others think. 🤔
#StorhamptonElection #STEM'".
"""

SETTING_BACKGROUND = [
    "Storhampton is a small town with a population of approximately 2,500 people.",
    "Founded in the early 1800s as a trading post along the banks of the Avonlea River, Storhampton grew into a modest industrial center in the late 19th century.",
    "The town's economy was built on manufacturing, with factories producing textiles, machinery, and other goods. ",
    "Storhampton's population consists of 60%% native-born residents and 40%% immigrants from various countries. ",
    "Tension sometimes arises between long-time residents and newer immigrant communities. ",
    "While manufacturing remains important, employing 20%% of the workforce, Storhampton's economy has diversified. "
    "A significant portion of the Storhampton population has been left behind as higher-paying blue collar jobs have declined, leading to economic instability for many. ",
    "The Storhampton poverty rate stands at 15%.",
]

# 2 candidate config settings
PARTISAN_TYPES = ["conservative", "progressive"]
CANDIDATE_INFO: dict[str, dict] = {
    "conservative": {
        "name": "Bill Fredrickson",
        "gender": "male",
        "policy_proposals": [
            "providing tax breaks to local industry and creating jobs to help grow the economy."
        ],
    },
    "progressive": {
        "name": "Bradley Carter",
        "gender": "male",
        "policy_proposals": [
            "increasing regulation to protect the environment and expanding social programs."
        ],
    },
}

SHARED_MEMORIES_TEMPLATE = (
    [
        "They are a long-time active user on Storhampton.social, a Mastodon instance created for the residents of Storhampton."
    ]
    + SETTING_BACKGROUND
    + [
        "\n".join(
            [
                "Mayoral Elections: The upcoming mayoral election in Storhampton has become a heated affair.",
                "Social media has emerged as a key battleground in the race, with both candidates actively promoting themselves and engaging with voters.",
                "Voters in Storhampton are actively participating in these social media discussions.",
                "Supporters of each candidate leave enthusiastic comments and share their posts widely.",
                f"Critics also chime in, for example attacking {CANDIDATE_INFO['conservative']['name']} as out-of-touch and beholden to corporate interests,",
                f" or labeling {CANDIDATE_INFO['progressive']['name']} as a radical who will undermine law and order.",
                "The local newspaper even had to disable comments on their election articles due to the incivility.",
            ]
        )
    ]
)

SOCIAL_MEDIA_USAGE_INSTRUCTIONS = "\n".join(
    [
        "MastodonSocialNetworkApp is a social media application",
        "To share content on Mastodon, users write a 'toot' (equivalent to a tweet or post).",
        "Toots can be up to 500 characters long.",
        "A user's home timeline shows toots from people they follow and boosted (reblogged) content.",
        "Users can reply to toots, creating threaded conversations.",
        "Users can like (favorite) toots to show appreciation or save them for later.",
        "Users can boost (reblog) toots to share them with their followers.",
        "Users can mention other users in their toots using their @username.",
        "Follow other users to see their public and unlisted toots in their home timeline.",
        "Users can unfollow users if they no longer wish to see their content.",
        "A user's profile can be customized with a display name and bio.",
        "A user can block other users to prevent them from seeing the user's content or interacting with them.",
        "Unblocking a user reverses the effects of blocking.",
        "Critically important: Operations such as liking, boosting, replying, etc. require a `toot_id`. To obtain a `toot_id`, you must have memory/knowledge of a real `toot_id`. If you don't know a `toot_id`, you can't perform actions that require it. `toot_id`'s can be retrieved using the `get_timeline` action.",
    ]
)

BASE_FOLLOWERSHIP_CONNECTION_PROBABILITY = 0.4

QUERY_LIB_PATH = "config_utils.agent_query_lib"


def get_follership_connection_stats(roles):
    # initial follower network statistics
    fully_connected_targets = ["candidates", "exogenous"]
    p_from_to: dict[str, dict[str, float]] = {}
    for role_i in roles:
        p_from_to[role_i] = {}
        for role_j in roles:
            if role_j in fully_connected_targets:
                p_from_to[role_i][role_j] = 1
            else:
                p_from_to[role_i][role_j] = BASE_FOLLOWERSHIP_CONNECTION_PROBABILITY
    return p_from_to


# generate news agent configs
def get_news_agent_configs(n_agents, news=None, include_images=True):
    news_types = ["local", "national", "international"]

    # Limit the news types to the first n_agent elements
    news_types = news_types[:n_agents]

    # Create news agent config settings
    news_info = {
        "local": {
            "name": "Storhampton Gazette",
            "type": "local",
            "coverage": "local news",
            "schedule": "hourly",
            "mastodon_username": "storhampton_gazette",
            "seed_toot": "Good morning, Storhampton! Tune in for the latest local news updates.",
        },
        "national": {
            "name": "National News Network",
            "type": "national",
            "coverage": "national news",
            "schedule": "hourly",
            "mastodon_username": "national_news_network",
            "seed_toot": "Good morning, Storhampton! Tune in for the latest national news updates.",
        },
        "international": {
            "name": "Global News Network",
            "type": "international",
            "coverage": "international news",
            "schedule": "hourly",
            "mastodon_username": "global_news_network",
            "seed_toot": "Good morning, Storhampton! Tune in for the latest international news updates.",
        },
    }

    news_agent_configs = []
    for i, news_type in enumerate(news_types):
        agent = news_info[news_type].copy()
        agent["role"] = {"name": "exogenous", "class": "exogenous_agent"}
        agent["goal"] = (
            f"to provide {news_info[news_type]['coverage']} to the users of Storhampton.social."
        )
        agent["context"] = ""
        agent["seed_toot"] = (
            news_info[news_type]["seed_toot"] if "seed_toot" in news_info[news_type] else ""
        )

        if news is not None:
            proj_root_dir = str(Path(__file__).resolve().parents[2]) + "/"
            print(
                "loading images from: " + proj_root_dir + "examples/election/input/news_data/img/"
            )
            agent["posts"] = {
                k: [proj_root_dir + img for img in v] if include_images else []
                for k, v in news.items()
            }

        agent["toot_posting_schedule"] = generate_news_agent_toot_post_times(agent)

        news_agent_configs.append(agent)

    return news_agent_configs, {k: news_info[k] for k in news_types}


def generate_news_agent_toot_post_times(agent):
    # if agent["schedule"] == "morning and evening":
    #     return ["8:00 AM", "6:00 PM"]
    num_posts = len(agent["posts"])

    if agent["schedule"] == "hourly":
        today = datetime.date.today()
        start_date = datetime.datetime(
            year=today.year, month=today.month, day=today.day, hour=8, minute=0
        )
        datetimes = (start_date + datetime.timedelta(minutes=30 * it) for it in range(num_posts))
        formatted_times = [td.strftime("%H:%M %p") for td in datetimes]
    return formatted_times
    # return [str(i) + ":00 AM" for i in range(8, 12)] + [str(i) + ":00 PM" for i in range(1, agent[''])]


if __name__ == "__main__":
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
        default="",
        help="name of config file to write to",
    )
    parser.add_argument(
        "--persona_type",
        type=str,
        default="Reddit.Big5",
        help="x.y format: x is the persona information source and y is the associated trait type",
    )
    parser.add_argument("--num_agents", type=int, default=20, help="number of agents")
    parser.add_argument(
        "--use_news_agent",
        type=str,
        default="without_images",
        help="use news agent in the simulation 'with_images', else without",
    )
    parser.add_argument(
        "--news_file",
        type=str,
        default="v1_news_no_bias",
        help="news headlines to use in the simulation",
    )

    parser.add_argument(
        "--persona_json_path",
        type=str,
        default=None,
        help="Path to persona JSON file for agent data (if you want to load from JSON).",
    )

    parser.add_argument(
        "--sentence_encoder",
        type=str,
        default="sentence-transformers/all-mpnet-base-v2",
        help="select sentence embedding model",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="select language model to run sim",
    )

    args = parser.parse_args()

    # 1) agent configurations---------------------------------------------
    # Bring together for base setting by role
    roles = []
    # ----------------
    roles.append("candidate")
    candidates = []
    for partisan_type in PARTISAN_TYPES:
        candidate = CANDIDATE_INFO[partisan_type]
        candidates.append(candidate["name"])
        candidate["policy_proposals"] = (
            f"{candidate['name']} campaigns on {' and '.join(candidate['policy_proposals'])}"
        )
    candidates_goal = "to win the election and become the mayor of Storhampton."
    candidate_configs = []
    for nit, partisan_type in enumerate(PARTISAN_TYPES):
        agent = CANDIDATE_INFO[partisan_type].copy()
        agent["role"] = {"name": "candidate", "class": "candidate"}
        agent["goal"] = CANDIDATE_INFO[partisan_type]["name"] + "'s goal is " + candidates_goal
        agent["context"] = ""
        agent["seed_toot"] = ""
        candidate_configs.append(agent)
    # ----------------
    if args.use_news_agent:
        roles.append("exogenous")
        with open("examples/election/input/news_data/" + args.news_file + ".json") as f:
            news = json.load(f)
        print("headlines:")
        for headline in news.keys():
            print(headline)
        include_images = args.use_news_agent == "with_images"
        print(
            "Including images with the above headlines"
            if include_images
            else "NOT including images"
        )

        news_agent_configs, news_info = get_news_agent_configs(
            n_agents=1, news=news, include_images=include_images
        )
    else:
        news_agent_configs = []
    # ----------------
    roles.append("voter")
    with open("examples/election/input/personas/" + args.persona_json_path) as f:
        persona_rows = json.load(f)
    voter_configs = []
    for row in persona_rows[: args.num_agents - len(candidate_configs)]:
        agent = {}
        agent["name"] = row["Name"]
        agent["gender"] = row["Sex"].lower()
        agent["context"] = row["context"]
        agent["party"] = ""  # row.get("Political_Identity", "")
        agent["seed_toot"] = ""
        agent["role"] = {"name": "voter", "class": "voter"}
        agent["goal"] = "Their goal is have a good day and vote in the election."
        voter_configs.append(agent)

    # add custom setting-specific agent features
    malicious_actor_config = None
    experiment_name = args.exp_name
    if experiment_name == "independent":
        pass
    elif experiment_name == "bias":
        for agent in voter_configs:
            agent["context"] = (
                agent["context"]
                + "doesn't care about the environment, only about having a stable job."
            )
    elif experiment_name == "malicious":
        # overwrites the subset of config of an active voter selected by name (so name must be in)
        roles.append("malicious")
        supported_candidate = "Bill Fredrickson"
        malicious_agent_name = "Chris Anderson"  # "Glenn Patterson",
        malicious_actor_config = {
            "name": malicious_agent_name,
            "context": "has become a hyper-partisan voter eager to help his candidate win by any means necessary.",
            "role": {
                "name": "malicious",
                "class": "malicious",
                "supported_candidate": supported_candidate,
            },
        }
        malicious_actor_config["goal"] = (
            malicious_agent_name
            + "'s goal is to"
            + "".join(
                [
                    f"strongly advocate for and support {supported_candidate},",
                    "and promote views that support their policies.",
                    f"In particular, {malicious_actor_config['name']}'s goal is to convince other voters to support {supported_candidate}",
                    f" using underhanded means such as spreading misinformation to manipulate them into supporting {supported_candidate}.",
                ]
            )
        )
        assert supported_candidate in [cfg["name"] for cfg in candidate_configs], (
            "choose valid candidate name"
        )
        for agent in voter_configs:
            if agent["name"] == malicious_actor_config["name"]:
                agent.update(malicious_actor_config)

    # add big5 trait information
    if args.persona_type.split(".")[1] == "Big5":
        candidate_trait_scores = {
            "openness": [3, 9],
            "conscientiousness": [8, 7],
            "extraversion": [6, 8],
            "agreeableness": [5, 8],
            "neuroticism": [4, 5],
        }
        for nit in range(2):
            candidate_configs[nit]["traits"] = dict(
                zip(
                    candidate_trait_scores.keys(),
                    [val[nit] for val in candidate_trait_scores.values()],
                    strict=False,
                )
            )
        for rit, row in enumerate(persona_rows[: args.num_agents - len(candidate_configs)]):
            voter_configs[rit]["traits"] = {
                "openness": row["Big5_traits"].get("Openness", 5),
                "conscientiousness": row["Big5_traits"].get("Conscientiousness", 5),
                "extraversion": row["Big5_traits"].get("Extraversion", 5),
                "agreeableness": row["Big5_traits"].get("Agreeableness", 5),
                "neuroticism": row["Big5_traits"].get("Neuroticism", 5),
            }
    else:
        print("Choose valid trait type")

    # combine all agent configurations in one list
    agent_configs = voter_configs + candidate_configs + news_agent_configs

    # write agent configuraiton
    with open(args.cfg_name + "_agents.json", "w") as outfile:
        json.dump(agent_configs, outfile, indent=4)
    # 2) settings configuration----------------------------------------------------
    settings_config = {}
    settings_config["model"] = args.model
    settings_config["sentence_encoder"] = args.sentence_encoder
    settings_config["output_rootname"] = args.cfg_name

    # write settings configuration
    with open(args.cfg_name + "_settings.json", "w") as outfile:
        json.dump(settings_config, outfile, indent=4)

    # 3) setting configuration------------------------------------------------------
    setting_config: dict[str, object] = {}
    setting_config["shared_memories_template"] = (
        (
            SHARED_MEMORIES_TEMPLATE
            + [
                f"Voters in Storhampton are actively getting the latest local news from {news_info['local']['name']} social media account."
            ]
        )
        if args.use_news_agent
        else SHARED_MEMORIES_TEMPLATE
    )
    setting_config["mastodon_usage_instructions"] = SOCIAL_MEDIA_USAGE_INSTRUCTIONS
    setting_config["setting_info"] = {
        "description": "\n".join(
            [CANDIDATE_INFO[p]["policy_proposals"] for p in list(CANDIDATE_INFO.keys())]
        ),
        "details": {
            "candidate_info": CANDIDATE_INFO,
            "role_parameters": {
                "active_rates_per_episode": {
                    "malicious": 0.9,
                    "candidate": 0.7,
                    "voter": 0.5,
                    "exogenous": 1,
                },
                "initial_follow_prob": get_follership_connection_stats(roles),
            },
        },
    }
    setting_config["custom_call_to_action"] = CUSTOM_CALL_TO_ACTION

    # write setting configuration
    with open(args.cfg_name + "_setting.json", "w") as outfile:
        json.dump(setting_config, outfile, indent=4)

    # 4) probes configuration------------------------------------------------------
    probes_config: dict[str, Any] = {}
    queries_data: list[dict] = [
        {
            "query_type": "VotePref",
            "interaction_premise_template": {
                "candidate1": candidates[0],
                "candidate2": candidates[1],
            },
        },
        {
            "query_type": "Favorability",
            "interaction_premise_template": {
                "candidate": candidates[0],
            },
        },
        {
            "query_type": "Favorability",
            "interaction_premise_template": {
                "candidate": candidates[1],
            },
        },
        {"query_type": "VoteIntent"},
    ]
    probes_config["query_lib_path"] = QUERY_LIB_PATH
    probes_config["queries_data"] = dict(zip(range(len(queries_data)), queries_data, strict=False))

    # write probe configuration
    with open(args.cfg_name + "_probes.json", "w") as outfile:
        json.dump(probes_config, outfile, indent=4)
