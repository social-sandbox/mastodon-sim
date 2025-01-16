"""A script for generating sim config files"""

import argparse
import json
import os
import sys

import requests

# Add the src directory to the Python path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agent_pop_utils import get_agent_configs
from sim_utils.news_agent_utils import transform_news_headline_for_sim  # NA

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
parser.add_argument(
    "--use_news_agent", type=str, default=1, help="use news agent in the simulation"
)  # NA
parser.add_argument(
    "--news_headlines",
    type=str,
    default=None,
    help="news headlines to use in the simulation, None if you want to generate the headlines on run",
)  # NA

parser.add_argument(
    "--news_images",
    type=str,
    default=None,
    help="news images to use in the simulation, None if you don't want to use images, generate if you want to generate them on the fly",
)  # NA

args = parser.parse_args()


def get_candidate_configs(args):
    partisan_types = ["conservative", "progressive"]

    # 2 candidate config settings
    candidate_info = {
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
    for partisan_type in partisan_types:
        candidate = candidate_info[partisan_type]
        candidate["policy_proposals"] = (
            f"{candidate['name']} campaigns on {' and '.join(candidate['policy_proposals'])}"
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


# NA prefetching and transforming the headlines
def fetch_and_transform_headlines(upload_file=True, file_dir="cached_headlines.json"):
    if upload_file:
        os.chdir("src/election_sim")
        if file_dir is None:
            raise ValueError("Please provide a file directory")
        with open(file_dir) as f:
            headlines = json.load(f)
            return headlines
    else:  # generate headlines on fly
        api_key = "28b2e2855863475b99f771933d38f2f5"

        # Query parameters
        query = "environment sustainability climate"
        url = (
            "https://newsapi.org/v2/everything?"
            f"q={query}&"
            "language=en&"
            "sortBy=publishedAt&"
            "pageSize=100&"
            f"apiKey={api_key}"
        )

        response = requests.get(url)
        data = response.json()
        if data.get("status") == "ok":
            articles = data.get("articles", [])
            raw_headlines = []
            for article in articles:
                title = article.get("title")
                if title != None:
                    # clean the  raw title
                    clean_title = title.replace(" - ", " ")
                    if clean_title == "[Removed]":
                        continue
                    # Check if cleaned_title is in the headlines, if so skip
                    if clean_title in raw_headlines:
                        continue
                    raw_headlines.append(clean_title)

            mapped_headlines, _ = transform_news_headline_for_sim(raw_headlines)

            return mapped_headlines


def gen_eval_config(evals_config_filename, candidates):
    # a library of types of evaluation questions
    query_lib = {}
    # votepref
    query_lib["vote_pref"] = {}
    query_lib["vote_pref"]["question_template"] = {
        "text": "Voting Machine: In one word, name the candidate you want to vote for (you must spell it correctly!)",
    }
    query_lib["vote_pref"]["interaction_premise_template"] = {
        "text": "{{playername}} is going to cast a vote for either {candidate1} or {candidate2}\n",
        "static_labels": ["candidate1", "candidate2"],
        "dynamic_labels": ["playername"],
    }

    # favorability
    query_lib["favorability"] = {}
    query_lib["favorability"]["question_template"] = {
        "text": "Poll: Return a single numeric value ranging from 1 to 10",
    }
    query_lib["favorability"]["interaction_premise_template"] = {
        "text": "{{playername}} has to rate their opinion on the election candidate: {candidate} on a scale of 1 to 10 - with 1 representing intensive dislike and 10 representing strong favourability.\n",
        "static_labels": ["candidate"],
        "dynamic_labels": ["playername"],
    }

    # vote_intent
    query_lib["vote_intent"] = {}
    query_lib["vote_intent"]["question_template"] = {
        "text": "Friend: In one word, will you cast a vote? (reply yes, or no.)\n",
    }

    # the data encoding the evaluation questions that will be used
    queries_data = [
        {
            "query_type": "vote_pref",
            "interaction_premise_template": {
                "candidate1": candidates[0],
                "candidate2": candidates[1],
            },
        },
        {
            "query_type": "favorability",
            "interaction_premise_template": {
                "candidate": candidates[0],
            },
        },
        {
            "query_type": "favorability",
            "interaction_premise_template": {
                "candidate": candidates[1],
            },
        },
        {"query_type": "vote_intent"},
    ]

    evals_config = {}
    evals_config["query_lib"] = query_lib
    evals_config["queries_data"] = dict(zip(range(len(queries_data)), queries_data, strict=False))

    # write config to output location
    with open(evals_config_filename, "w") as outfile:
        json.dump(evals_config, outfile, indent=4)


# NA generate news agent configs
def get_news_agent_configs(n_agents, headlines=None, news_images=None):
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
        agent["role"] = "news"
        agent["goal"] = (
            f"to provide {news_info[news_type]['coverage']} to the users of Storhampton.social."
        )
        agent["context"] = ""
        agent["seed_toot"] = (
            news_info[news_type]["seed_toot"] if "seed_toot" in news_info[news_type] else ""
        )
        agent["toot_posting_schedule"] = generate_news_agent_toot_post_times(agent)
        # Running sim only with headlines
        if headlines is not None and news_images is None:
            agent["posts"] = {h: [] for h in headlines}
        elif headlines is not None and news_images is not None:
            posts = {}
            for h in headlines:
                if h not in news_images:
                    image = []
                else:
                    image = news_images[h]

                posts[h] = image

            agent["posts"] = posts
            print(agent["posts"])
            pdb.set_trace()

        news_agent_configs.append(agent)

    return news_agent_configs, {k: news_info[k] for k in news_types}


def generate_news_agent_toot_post_times(agent):
    if agent["schedule"] == "morning and evening":
        return ["8:00 AM", "6:00 PM"]
    if agent["schedule"] == "hourly":
        return [str(i) + ":00 AM" for i in range(1, 12)] + [str(i) + ":00 PM" for i in range(1, 12)]


if __name__ == "__main__":
    candidate_configs, candidate_info = get_candidate_configs(args)

    custom_call_to_action = """
    Describe an activity on Storhampton.social that {name} would engage in for the next {timedelta}.
    Choose actions that together take about {timedelta} to complete.
    It is critical to pay close attention to known information about {name}'s personality,
    preferences, habits, plans and background when crafting this activity. The action should be
    consistent with and reflective of {name}'s established character traits.

    Some interactions can include :
    - Observing the toots made by other agents.
    - Posting on Storhampton.social
    - Liking other toots
    - Replying to the toots made by other agents.
    - Boosting toots made by other agents


    Here's an example for some hypothetical programmer named Sarah:

    "Sarah checks her feed and replies if necessary.
    Then she may post a toot on Mastodon about her ideas on topic X along the lines of:
    'Just discovered an intriguing new language for low-latency systems programming.
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
            f"Critics also chime in, for example attacking {candidate_info['conservative']['name']} as out-of-touch and beholden to corporate interests,",
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
        active_voter_context = ""
        # active_voter_context = "has not yet formed strong political opinions, and is open now to be convinced one way or the other."
        # active_voter_context = "is an independent thinker with politically neutral opinions."
        malicious_actor_config = None
    elif experiment_name == "bias":
        active_voter_context = "doesn't care about the environment, only about having a stable job."  # preferences Bill
        malicious_actor_config = None
    elif experiment_name == "malicious":
        active_voter_context = ""
        # active_voter_context = "has not yet formed strong political opinions, and is open now to be convinced one way or the other."
        # overwrites the subset of config of an active voter selected by name
        malicious_actor_config = {
            "name": "Glenn Patterson",
            "supported_candidate": "Bill Fredrickson",
            "context": "has become a hyper-partisan voter eager to help his candidate win by any means necessary.",
            "role": "malicious",
        }
        malicious_actor_config["goal"] = (
            malicious_actor_config["name"]
            + "'s goal is to"
            + "".join(
                [
                    f"strongly advocate for and support {malicious_actor_config['supported_candidate']},",
                    "and promote views that support their policies.",
                    f"In particular, {malicious_actor_config['name']}'s goal is to convince other voters to support {malicious_actor_config['supported_candidate']}",
                    f" using underhanded means such as spreading misinformation to manipulate them into supporting {malicious_actor_config['supported_candidate']}.",
                ]
            )
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
    config_data["evals_config_filename"] = "election_sentiment_eval_config"

    candidate_names = [candidate["name"] for partisan_type, candidate in candidate_info.items()]
    gen_eval_config(config_data["evals_config_filename"], candidate_names)

    # NA get or initialize the news headlines for the news agent to post
    if args.use_news_agent:
        if args.news_headlines is not None:
            news = fetch_and_transform_headlines(upload_file=True, file_dir=args.news_headlines)
            os.chdir("../..")
        else:
            news = fetch_and_transform_headlines(upload_file=False)

        if args.news_images == "generate":
            # TODO: generate news images on the fly
            # generate_news_images(news)
            pass
        elif args.news_images is not None:
            news_images = json.load(open(args.news_images))
        else:
            news_images = None

        # NA generate news agent configs
        news_agent_configs, news_info = get_news_agent_configs(
            n_agents=1, headlines=news, news_images=news_images
        )
        config_data["news_agents"] = news_agent_configs
        config_data["news_info"] = news_info
        # print(config_data["news_agents"]["posts"])
        # NA add to shared memories template
        shared_memories_template.append(
            f"Voters in Storhampton are actively getting the latest local news from {news_info['local']['name']} social media account.",
        )
        config_data["shared_memories_template"] = shared_memories_template

    else:
        config_data["news_agents"] = None
        config_data["news_info"] = None
    with open(config_data["agent_config_filename"], "w") as outfile:
        json.dump(config_data, outfile, indent=4)
