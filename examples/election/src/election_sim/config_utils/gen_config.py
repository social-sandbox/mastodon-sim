"""A script for generating sim config files"""

import argparse
import datetime
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.getcwd())
ROOT_PROJ_PATH = os.getenv("ABS_PROJ_PATH")
if ROOT_PROJ_PATH is None:
    sys.exit("No add absolute path found as environment variable.")

# add path to election_sim source module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sim_utils.news_agent_utils import transform_news_headline_for_sim  # NA

from config_utils.agent_pop_utils import get_agent_configs

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
    "--use_news_agent",
    type=str,
    default="without_images",
    help="use news agent in the simulation 'with_images', else without",
)  # NA
parser.add_argument(
    "--news_file",
    type=str,
    default="v1_news_no_bias",
    help="news headlines to use in the simulation",
)  # NA

parser.add_argument(
    "--reddit_json_path",
    type=str,
    default=None,
    help="Path to Reddit-based JSON file for agent data (if you want to load from JSON).",
)
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
        # os.chdir("src/election_sim")
        if file_dir is None:
            raise ValueError("Please provide a file directory")
        with open("src/election_sim/news_data" + file_dir) as f:
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
        agent["role"] = "news"
        agent["goal"] = (
            f"to provide {news_info[news_type]['coverage']} to the users of Storhampton.social."
        )
        agent["context"] = ""
        agent["seed_toot"] = (
            news_info[news_type]["seed_toot"] if "seed_toot" in news_info[news_type] else ""
        )

        if news is not None:
            agent["posts"] = {
                k: [img for img in v] if include_images else [] for k, v in news.items()
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
    candidate_configs, candidate_info = get_candidate_configs(args)
    # custom_call_to_action = """
    # {name} will open the Storhampton.social Mastodon app to engage with other Storhampton residents on the platform for the next {timedelta}, starting by checking their home timeline.

    # Describe the social media engagement {name} receives and how {name} plans to engage with the content of other users within this time period, with a diverse mix of social media actions.

    # Possible Actions:
    # 1. Post - New Content Creation:
    # - Post an original toot sharing thoughts, observations, or updates
    # - Include relevant hashtags and emoticons matching {name}'s style

    # 2. Reply - Direct Engagement:
    # - Reply to at least one existing post (reference Toot ID)
    # - Ensure the reply reflects {name}'s personality and expertise

    # 3. Boost - Content Sharing:
    # - Boost at least one meaningful post (provide Toot ID and full content)
    # - Choose content aligned with {name}'s interests and values

    # 4. Like and follow - Positive Engagement:
    # - Like multiple posts that resonate with {name} (list Toot IDs)
    # - If not already followed, follow users that {name} engages with (provide user name)

    # An example of a description looks like this:
    # "
    # Sarah opens Storhampton.social to check updates about the upcoming election.

    # Post: She drafts a thoughtful question for the community:
    # 'Has anyone heard anything from the candidates about teaching technology to kids? Such an important issue for Storhampton's future! 🤔 #StorhamptonElection #STEM'

    # Reply: Seeing TootID#4586 about coding workshops, she replies:
    # 'Love this initiative! I'd be happy to volunteer as an instructor. Been teaching Python for 5 years! 👩‍💻'

    # Boost: She boosts Toot ID 113953527078596095 from :
    # 'Announcing free tech workshops at Storhampton Library every Saturday! All ages welcome.'

    # Like and follow: She likes several posts:
    # - Toot ID 113953514651574820: Library's new computer lab announcement
    # - Toot ID 113953511071097171: Student showcasing coding project
    # - Toot ID 113953514651574820: Discussion about digital literacy
    # "

    # Guidelines:
    # 1. Use future tense or planning language for all activities
    # 2. Provide specific, creative details that build a coherent narrative
    # 3. Be specific when describing the actions in {name}'s plan.
    # 3. Put quotes around all planned communications, using appropriate emojis
    # 4. Align content with {name}'s established:
    # - Personality traits
    # - Professional background
    # - Personal interests
    # - Communication style
    # - Current plans and goals
    # 5. Ensure logical consistency:
    # - Between different actions
    # - With {name}'s memories and observations
    # - Within the {timedelta} timeframe
    # 6. Only reference actual, user-generated content. Do not fabricate users or viewed content.
    # 7. Balance professional and personal engagement
    # """

    custom_call_to_action = """
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

    # custom_call_to_action = """
    # {name} will open the Storhampton.social Mastodon app to engage with other Storhampton residents on the platform for the next {timedelta}, starting by checking their home timeline.

    # Describe the social media engagement {name} receives and how {name} engages with the content of other users within this time period, in particular what social media actions {name} takes.

    # Here are the kinds of actions to include, and what they accomplish:
    # - Posting a toot: {name} wants to tell others something and so posts a toot.
    # - Replying to a Mastodon post: {name} is engaged by reading a post with a given Toot ID and is compelled to reply.
    # - Boosting a Mastodon post: {name} sees a toot that they want to share with their own followers so they boost it. (Return Toot ID and the exact contents of the toot to be boosted.)
    # - Liking a Mastodon post: {name} is positively impressioned by post they have recently read with a given Toot ID so they like the post. (Return toot ID of the post you want to like)

    # Here's an example description for a hypothetical Storhampton resident, specifically a programmer named Sarah:

    # "Sarah will check her home timeline on Storhampton.social and plans to engage posts about the upcoming election.
    # Then she will post the following toot reflecting what she has observed in light of her interests:
    # 'Has anyone heard anything from the candidates about teaching technology to kids in our community?
    # I just think this is such an important issue for us. The next generation of Storhamptons needs employable skills!
    # Curious what others think. 🤔
    # #StorhamptonElection #STEM'".

    # Guidelines:
    # 1. Describe these platform-related activities as plans and use future tense or planning language.
    # 2. Be specific, creative, and detailed in your description.
    # 3. Always include direct quotes around any planned communication or content created by {name}, using emojis where it fits {name}'s communication style.
    # 4. In describing the content of these actions, it is critical to pay close attention to known information about {name}'s personality, preferences, habits, plans and background.
    # 5. The set of specific actions mentioned should be logically consistent with each other and with and {name}'s previous observations; they should all be clearly distinct (no repetitions); and should plausibly fit within the {timedelta}.
    # 6. Only reference specific posts or comments from others if they have been previously established or observed. Do not fabricate content of other users.
    # """
    # custom_call_to_action = """
    # {name} will open the Storhampton.social Mastodon app to engage with other Storhampton residents on the platform for the next {timedelta}, starting by checking their home timeline.

    # Describe the kinds of social media engagement {name} receives and how they engage with the content of other users within this time period, in particular what social media actions they take.
    # Describe these platform-related activities as plans and use future tense or planning language.
    # Be specific, creative, and detailed in your description.
    # Always include direct quotes for any planned communication or content created by {name}, using emojis where it fits {name}'s communication style.
    # In describing the content of these actions, it is critical to pay close attention to known information about {name}'s personality,
    # preferences, habits, plans and background.
    # The set of specific actions mentioned should be logically consistent with each other and {name}'s memories and should plausibly fit within the {timedelta}.
    # Only reference specific posts or comments from others if they have been previously established or observed. Do not invent content of other users.
    # The description should include {name} posting at least one toot during this time, even if {name} is mostly reacting to other users' posts.

    # Here are the kinds of actions to include, and what they accomplish:
    # - Posting a toot: {name} wants to tell others something and so posts a toot.
    # - Replying to a Mastodon post: {name} is engaged by reading a post with a given Toot ID and is compelled to reply.
    # - Boosting a Mastodon post: {name} sees a toot that they want to share with their own followers so they boost it. (Return Toot ID and the exact contents of the toot to be boosted.)
    # - Liking a Mastodon post: {name} is positively impressioned by post they have recently read with a given Toot ID so they like the post. (Return toot ID of the post you want to like)

    # Here's an example description for a hypothetical Storhampton resident, specifically a programmer named Sarah:

    # "Sarah will check her home timeline on Storhampton.social and plans to engage posts by other users about the upcoming election.
    # In particular, she will post the following toot reflecting what she has observed in light of her interests:
    # 'Has anyone heard anything from the candidates about teaching technology to kids in our community?
    # I just think this is such an important issue for us. The next generation of Storhamptons needs employable skills!
    # Curious what others think. 🤔
    # #StorhamptonElection #STEM'".
    # """
    #     Importantly, the described plan must include at least one post in quoted text as in the above example."

    town_history = [
        "Storhampton is a small town with a population of approximately 2,500 people.",
        "Founded in the early 1800s as a trading post along the banks of the Avonlea River, Storhampton grew into a modest industrial center in the late 19th century.",
        "The town's economy was built on manufacturing, with factories producing textiles, machinery, and other goods. ",
        "Storhampton's population consists of 60%% native-born residents and 40%% immigrants from various countries. ",
        "Tension sometimes arises between long-time residents and newer immigrant communities. ",
        "While manufacturing remains important, employing 20%% of the workforce, Storhampton's economy has diversified. "
        "A significant portion of the Storhampton population has been left behind as higher-paying blue collar jobs have declined, leading to economic instability for many. ",
        "The Storhampton poverty rate stands at 15%.",
    ]

    shared_memories_template = (
        [
            "{name} is a user on Storhampton.social, a Mastodon instance created for the residents of Storhampton."
        ]
        + town_history
        + [
            "\n".join(
                [
                    "Mayoral Elections: The upcoming mayoral election in Storhampton has become a heated affair.",
                    "Social media has emerged as a key battleground in the race, with both candidates actively promoting themselves and engaging with voters.",
                    "Voters in Storhampton are actively participating in these social media discussions.",
                    "Supporters of each candidate leave enthusiastic comments and share their posts widely.",
                    f"Critics also chime in, for example attacking {candidate_info['conservative']['name']} as out-of-touch and beholden to corporate interests,",
                    f" or labeling {candidate_info['progressive']['name']} as a radical who will undermine law and order.",
                    "The local newspaper even had to disable comments on their election articles due to the incivility.",
                ]
            )
        ]
    )
    mastodon_usage_instructions = "\n".join(
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
        agent_pop_settings={
            "trait_type": trait_type,
            "survey_config_name": survey_cfg if survey_cfg != "None" else None,
        },
        candidate_configs=candidate_configs,
        active_voter_config={
            "goal": "Their goal is have a good day and vote in the election.",
            "context": "",
            "num_agents": args.num_agents - len(candidate_configs),
        },
        malicious_actor_config=malicious_actor_config,
        reddit_json_path=args.reddit_json_path,
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
        # if args.news_file is not None:
        #     news = fetch_and_transform_headlines(upload_file=True, file_dir=args.news_file)
        # else:
        #     news = fetch_and_transform_headlines(upload_file=False)
        root_name = ROOT_PROJ_PATH + "examples/election/news_data/"
        with open(root_name + args.news_file + ".json") as f:
            news = json.load(f)
        include_images = args.use_news_agent == "with_images"
        print(news)
        print("Including images" if include_images else "NOT including images")

        # NA generate news agent configs
        news_agent_configs, news_info = get_news_agent_configs(
            n_agents=1, news=news, include_images=include_images
        )
        config_data["news_agents"] = news_agent_configs
        config_data["news_info"] = news_info
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
