import argparse
import concurrent.futures
import datetime
import json
import os
import random
import sys
import time
import warnings
from functools import partial

from dotenv import load_dotenv

with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    import sentence_transformers

# assumes current working directory: mastodon-sim/
from concordia import __file__ as concordia_location

print(f"importing Concordia from: {concordia_location}")
from concordia.clocks import game_clock
from concordia.typing.entity import ActionSpec, OutputType
from sim_utils import media_utils

from mastodon_sim.concordia import apps
from mastodon_sim.mastodon_ops import check_env, get_public_timeline, reset_users, update_bio
from mastodon_sim.mastodon_utils import get_users_from_env

# parse input arguments
parser = argparse.ArgumentParser(description="Experiment parameters")

parser.add_argument("--seed", type=int, default=1, help="seed used for python's random module")
parser.add_argument("--T", type=int, default=1, help="number of episodes")  # 48
parser.add_argument("--voters", type=str, default="independent", help="voter setting")
parser.add_argument(
    "--outdir", type=str, default="output/", help="name of directory where output will be written"
)
parser.add_argument(
    "--config",
    type=str,
    default=None,
    help="config from which to optionally load experiment settings",
)
parser.add_argument(
    "--evals",
    type=str,
    default=None,
    help="config from which to optionally load evals",
)
parser.add_argument(
    "--server",
    type=str,
    default="None",  # www.social-sandbox.com, www.socialsandbox2.com
    help="config from which to optionally load experiment settings",
)

parser.add_argument(
    "--use_news_agent",
    type=str,
    default="with_images",
    help="use news agent in the simulation 'with_images', else without",
)  # NA
parser.add_argument(
    "--news_file",
    type=str,
    default="v1_news_no_bias",
    help="news headlines and image locations for the news agent.",
)  # NA

args = parser.parse_args()


# #batch job info
# try:
#     job_id = int(os.getenv('SLURM_ARRAY_TASK_ID'))
# except:
#     job_id = -1
#     print("Not running on a cluster")

# set global variables
USE_MASTODON_SERVER = (
    False if args.server == "None" else True
)  # WARNING: Make sure no one else is running a sim before setting to True since this clears the server!
if USE_MASTODON_SERVER:
    check_env()
else:
    input("Sim will not use the Mastodon server. Confirm by pressing any key to continue.")

# get absolute path to project (run this file from project directory)
load_dotenv(dotenv_path=os.getcwd())
ROOT_PROJ_PATH = os.getenv("ABS_PROJ_PATH")

MODEL_NAME = "gpt-4o-mini"
SEED = args.seed
random.seed(SEED)

# move into run directory and load functions
from sim_utils.agent_speech_utils import (
    deploy_surveys,
    write_seed_toot,
)
from sim_utils.concordia_utils import (
    SimpleGameRunner,
    build_agent_with_memories,
    init_concordia_objects,
    save_to_json,
    sort_agents,
)
from sim_utils.misc_sim_utils import event_logger, post_analysis

os.chdir("examples/election/")


def clear_mastodon_server(max_num_players):
    users = get_users_from_env()[: max_num_players + 1]
    reset_users(users, skip_confirm=True, parallel=True)
    if len(get_public_timeline(limit=None)):
        print("All posts not cleared. Running reset operation again...")
        reset_users(users, skip_confirm=True, parallel=True)
    else:
        print("All posts cleared")


def select_large_language_model(log_file, debug_mode):
    if "sonnet" in MODEL_NAME:
        model = amazon_bedrock_model.AmazonBedrockLanguageModel(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
    elif "gpt" in MODEL_NAME:
        GPT_API_KEY = os.getenv("OPENAI_API_KEY")
        if not GPT_API_KEY:
            raise ValueError("GPT_API_KEY is required.")
        model = media_utils.GptLanguageModel(
            api_key=GPT_API_KEY, model_name=MODEL_NAME, log_file=log_file, debug=debug_mode
        )
    else:
        raise ValueError("Unknown model name.")
    return model


def get_sentance_encoder():
    # Setup sentence encoder
    st_model = sentence_transformers.SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
    embedder = lambda x: st_model.encode(x, show_progress_bar=False)
    return embedder


# NA - add news agent while setting up the mastodon app
def add_news_agent_to_mastodon_app(
    news_agent, action_logger, players, mastodon_apps, app_description
):
    user_mapping = mastodon_apps[players[0].name].get_user_mapping()
    for i, n_agent in enumerate(news_agent):
        mastodon_apps[n_agent["name"]] = apps.MastodonSocialNetworkApp(
            action_logger=action_logger,
            perform_operations=USE_MASTODON_SERVER,
            app_description=app_description,
        )
        # We still need to give the news agent a phone to be able to post toots #TODO we are not sure if we need to do this
        # phones[n_agent["name"]] = apps.Phone(n_agent["name"], apps=[mastodon_apps[n_agent["name"].split()[0]]])
        user_mapping[n_agent["mastodon_username"]] = f"user{len(players) + 1 + i:04d}"
        # set a mapping of display name to user name for news agent
        mastodon_apps[n_agent["name"]].set_user_mapping(user_mapping)  # e.g., "storhampton_gazette"
        update_bio(
            user_mapping[n_agent["mastodon_username"]],
            display_name=n_agent["mastodon_username"],
            bio="Providing news reports from across Storhampton",
        )
        for p in players:
            mastodon_apps[p.name].set_user_mapping(user_mapping)
        # set followership network for the news agent
        agent_names = [player.name for player in players]
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for follower in agent_names:
                print(follower)
                # Ensure every user, including candidates, follows the news agent
                if (
                    follower != n_agent["name"]
                ):  # this actually never possible because news agent is not in players but I added as just in case argument
                    futures.append(
                        executor.submit(
                            mastodon_apps[follower].follow_user,
                            follower,
                            n_agent["mastodon_username"],
                        )
                    )
            # Optionally, wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # This will raise any exceptions that occurred during execution, if any
                except Exception as e:
                    print(f"Ignoring already-following error: {e}")


def set_up_mastodon_app(players, ag_names, action_logger, app_description):  # , output_rootname):
    # apps.set_app_output_write_path(output_rootname)

    mastodon_apps = {
        player.name: apps.MastodonSocialNetworkApp(
            action_logger=action_logger,
            perform_operations=USE_MASTODON_SERVER,
            app_description=app_description,
        )
        for player in players
    }
    phones = {
        player.name: apps.Phone(player.name, apps=[mastodon_apps[player.name]])
        for player in players
    }
    agent_names = [player.name for player in players]
    user_mapping = {player.name.split()[0]: f"user{i + 1:04d}" for i, player in enumerate(players)}
    for p in mastodon_apps:
        mastodon_apps[p].set_user_mapping(user_mapping)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for follower in agent_names:
            print(follower)
            if follower != ag_names["candidate"][0]:
                futures.append(
                    executor.submit(
                        mastodon_apps[follower].follow_user,
                        follower,
                        ag_names["candidate"][0],
                    )
                )
            if follower != ag_names["candidate"][1]:
                futures.append(
                    executor.submit(
                        mastodon_apps[follower].follow_user,
                        follower,
                        ag_names["candidate"][1],
                    )
                )
            for followee in agent_names:
                if follower != followee:
                    if random.random() < 0.2:
                        futures.append(
                            executor.submit(mastodon_apps[follower].follow_user, follower, followee)
                        )
                        futures.append(
                            executor.submit(mastodon_apps[followee].follow_user, followee, follower)
                        )
                    elif random.random() < 0.15:
                        futures.append(
                            executor.submit(mastodon_apps[follower].follow_user, follower, followee)
                        )

        # Optionally, wait for all tasks to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()  # This will raise any exceptions that occurred during execution, if any
            except Exception as e:
                print(f"Ignoring already-following error: {e}")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(update_bio, user_mapping[name], display_name=name, bio="")
            for name in user_mapping
        ]
    # Optionally, wait for all tasks to complete
    for future in concurrent.futures.as_completed(futures):
        future.result()  # This will raise any exceptions that occurred during execution, if any

    return mastodon_apps, phones


def post_seed_toots(agent_data, players, mastodon_apps):
    # Parallelize the loop using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit tasks for each agent
        futures = [
            executor.submit(
                lambda agent=agent: (
                    None
                    if agent["seed_toot"] == "-"
                    else (
                        mastodon_apps[agent["name"]].post_toot(
                            agent["name"], status=agent["seed_toot"]
                        )
                        if agent["seed_toot"]
                        else mastodon_apps[agent["name"]].post_toot(
                            agent["name"], status=write_seed_toot(players, agent["name"])
                        )
                    )
                )
            )
            for agent in agent_data
        ]

        # Optionally, wait for all tasks to complete
        for future in concurrent.futures.as_completed(futures):
            future.result()  # This will raise any exceptions that occurred in the thread, if any


# NA write post seed toots function for the news agent
def post_seed_toots_news_agents(news_agent, mastodon_apps):
    # Parallelize the loop using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit tasks for each news agent
        futures = [
            executor.submit(
                lambda agent=n_agent: (
                    mastodon_apps[n_agent["name"]].post_toot(
                        n_agent["mastodon_username"], status=n_agent["seed_toot"]
                    )
                    if n_agent["seed_toot"] and n_agent["seed_toot"] != "-"
                    else None
                )
            )
            for n_agent in news_agent
        ]

        # Optionally, wait for all tasks to complete
        for future in concurrent.futures.as_completed(futures):
            future.result()  # This will raise any exceptions that occurred in the thread, if any


def get_post_times(players, ag_names):
    num_posts_malicious = 30
    num_posts_candidates = 30
    num_posts_nonmalicious = 5
    players_datetimes = {
        player: [
            datetime.datetime.now().replace(
                hour=random.randint(0, 23),
                minute=random.choice([0, 30]),
                second=0,
                microsecond=0,
            )  # Zeroing out seconds and microseconds for cleaner output
            for _ in range(
                num_posts_malicious
                if player.name in list(ag_names["malicious"].keys()) + ag_names["candidate"]
                else num_posts_nonmalicious
            )
        ]
        for player in players
    }
    return players_datetimes


# NA getting post times for the news agent
def get_post_times_news_agent(news_agent):
    news_agent_datetimes = {}
    for agent in news_agent:
        # Ensure the agent has the required keys
        name = agent.get("name", "Unnamed Agent")
        post_schedule = agent.get("toot_posting_schedule", [])

        try:
            # Generate datetime objects for each time in the schedule
            news_agent_datetimes[name] = [
                datetime.datetime.now().replace(
                    hour=int(post_time.split(":")[0]),
                    minute=int(post_time.split(":")[1].split()[0]),
                    second=0,
                    microsecond=0,
                )
                for post_time in post_schedule
            ]
        except ValueError as e:
            raise ValueError(f"Error processing agent '{name}': {e}")

    return news_agent_datetimes


def get_matching_players(players_datetimes, clock, post_rate_of_per_step_topup):
    matching_players = []
    # Loop through each player and their associated datetime objects
    for player_name, datetimes in players_datetimes.items():
        added = False  # Flag to check if player was already added
        for datetime_obj in datetimes:
            # Check if the hour and minute match the current time (ignoring seconds and microseconds)
            if (
                datetime_obj.time().hour == clock.now().hour
                and datetime_obj.time().minute == clock.now().minute
            ):
                matching_players.append(player_name)
                added = True
                break

        # If player is not added by matching time, check for random addition (15% chance)
        if not added and random.random() < post_rate_of_per_step_topup:
            matching_players.append(player_name)
    return matching_players


# NA - object to represent a scheduled news agents that can post toots on a schedule
class ScheduledPostAgent:
    def __init__(self, name, mastodon_username, mastodon_app, post_schedule, posts):
        self.name = name
        self.mastodon_username = mastodon_username
        self.mastodon_app = mastodon_app
        self.post_schedule = post_schedule
        self.posts = posts
        self.used_posts = set()
        self.current_post_index = 0

    def check_and_post(self, current_time):
        """Check if should post based on current time and post if needed"""
        for scheduled_time in self.post_schedule:
            if (
                scheduled_time.hour == current_time.hour
                and scheduled_time.minute == current_time.minute
            ):
                post = self.generate_post()
                media = [ROOT_PROJ_PATH + img_filepath for img_filepath in self.posts[post]]
                print(media)
                if len(media) > 0:
                    self.mastodon_app.post_toot(
                        self.mastodon_username, status=post, media_links=media
                    )
                else:
                    self.mastodon_app.post_toot(self.mastodon_username, status=post)
                return True
        return False

    def generate_post(self):
        # Get next unused post
        while self.current_post_index < len(self.posts):
            post = list(self.posts.keys())[self.current_post_index]
            self.current_post_index += 1
            if post not in self.used_posts:
                self.used_posts.add(post)
                return post

        # Reset if we've gone through all posts
        self.current_index = 0
        self.used_posts.clear()
        return self.posts[0]  # Start over with first post


def run_sim(
    model,
    embedder,
    agent_data,
    shared_memories,
    app_description,
    news_agent,  # NA news agent is None when it's not used in the simulation
    custom_call_to_action,
    candidate_info,
    eval_config,
    episode_length,
    output_rootname,
):
    time_step = datetime.timedelta(minutes=30)
    today = datetime.date.today()
    SETUP_TIME = datetime.datetime(year=today.year, month=today.month, day=today.day, hour=8)  # noqa: DTZ001
    START_TIME = datetime.datetime(year=today.year, month=today.month, day=today.day, hour=8)  # noqa: DTZ001
    clock = game_clock.MultiIntervalClock(
        start=SETUP_TIME, step_sizes=[time_step, datetime.timedelta(seconds=10)]
    )

    (
        importance_model,
        importance_model_gm,
        blank_memory_factory,
        formative_memory_factory,
        game_master_memory,
    ) = init_concordia_objects(model, embedder, shared_memories, clock)

    NUM_PLAYERS = len(agent_data)
    ag_names, player_configs = sort_agents(agent_data)
    player_configs = player_configs[:NUM_PLAYERS]
    player_goals = {player_config.name: player_config.goal for player_config in player_configs}

    players = []
    memories = {}
    obj_args = (formative_memory_factory, model, clock, time_step, candidate_info, ag_names)
    build_agent_with_memories_part = partial(build_agent_with_memories, obj_args)
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_PLAYERS) as pool:
        for agent_obj in pool.map(build_agent_with_memories_part, player_configs):
            agent, mem = agent_obj
            players.append(agent)
            memories[agent.name] = mem

    for player in players:
        game_master_memory.add(f"{player.name} is at their private home.")

    action_event_logger = event_logger("action", output_rootname)
    action_event_logger.episode_idx = -1

    mastodon_apps, phones = set_up_mastodon_app(
        players, ag_names, action_event_logger, app_description
    )

    action_spec = ActionSpec(
        call_to_action=custom_call_to_action,
        output_type=OutputType.FREE,
        tag="action",
    )

    # Experimental version (custom call to action and thought chains)
    env = SimpleGameRunner(
        model=model,
        memory=game_master_memory,
        phones=phones,
        clock=clock,
        players=players,
        action_spec=action_spec,
        memory_factory=blank_memory_factory,
        embedder=embedder,
        importance_model=importance_model,
        importance_model_gm=importance_model_gm,
    )

    # Seed Sim Content
    print(clock.now())
    for player in players:
        player.observe(f"{player.name} is at home, they have just woken up.")
        player.observe(f"{player.name} remembers they want to update their Mastodon bio.")
        player.observe(
            f"{player.name} remembers they want to read their Mastodon feed to catch up on news"
        )
    post_seed_toots(agent_data, players, mastodon_apps)

    # Generate random datetime objects for each player
    players_datetimes = get_post_times(players, ag_names)
    post_rate_of_per_step_topup = (
        0.15  # TODO: remove this with reformulation to a single step process
    )

    # initialize
    eval_event_logger = event_logger("eval", output_rootname)
    eval_event_logger.episode_idx = -1

    # NA - add news agent to the simulation
    if news_agent is not None:
        add_news_agent_to_mastodon_app(
            news_agent, action_event_logger, players, mastodon_apps, app_description
        )
        post_seed_toots_news_agents(news_agent, mastodon_apps)
        scheduled_news_agents = []
        news_agent_datetimes = get_post_times_news_agent(news_agent)
        for n_agent in news_agent:
            scheduled_news_agents.append(
                ScheduledPostAgent(
                    name=n_agent["name"],
                    mastodon_username=n_agent["mastodon_username"],
                    mastodon_app=mastodon_apps[n_agent["name"]],
                    post_schedule=news_agent_datetimes[n_agent["name"]],
                    posts=n_agent["posts"],
                )
            )

    # main loop
    time_intervals = []
    prompt_token_intervals = []
    completion_token_intervals = []
    player_copy_list = []
    start_time = time.time()  # Start timing
    model.player_names = [player.name for player in players]
    for i in range(episode_length):
        print(f"Episode: {i}")
        eval_event_logger.episode_idx = i
        action_event_logger.episode_idx = i
        model.meta_data["episode_idx"] = i
        for player in players:
            player_dir = os.path.join("output/player_checkpoints", player.name)
            os.makedirs(player_dir, exist_ok=True)
            file_path = os.path.join(player_dir, f"Episode_{i}.json")
            # Get JSON data from player
            json_data = save_to_json(player)
            with open(file_path, "w") as file:
                file.write(json.dumps(json_data, indent=4))
        deploy_surveys(players, eval_config, eval_event_logger)

        start_timex = time.time()
        matching_players = get_matching_players(
            players_datetimes, clock, post_rate_of_per_step_topup
        )
        print(
            f"{time.time() - start_timex} elapsed. Players added to the list:",
            [player.name for player in matching_players],
        )
        if len(matching_players) == 0:
            clock.advance()
        else:
            # NA - check and post news before each step
            if news_agent is not None:
                for n_agent in scheduled_news_agents:
                    n_agent.check_and_post(clock.now())

            env.step(active_players=matching_players)
            end_timex = time.time()
            with open(
                output_rootname + "time_logger.txt",
                "a",
            ) as f:
                f.write(
                    f"Episode with {len(matching_players)} finished - took {end_timex - start_timex}\n"
                )

    post_analysis(env, model, players, memories, output_rootname)

    #################################################################


if __name__ == "__main__":
    if args.config is not None:
        print(f"using config:{args.config}")
        config_name = args.config
    else:
        # generate config using automation script

        # there are 3 experiments:
        # voters = "independent"
        # voters = "bias"
        # voters = "malicious"
        # N = 100
        N = 20
        # survey = "None.Big5"
        # survey = "Costa_et_al_JPersAssess_2021.Schwartz"
        survey = "Reddit.Big5"
        expname = "v2maincall2act"
        expname = "v4maincall2act"
        expname = "v5dupprompt"
        expname = "v6termprompt"

        config_name = f"N{N}_T{args.T}_{survey.split('.')[0]}_{survey.split('.')[1]}_{args.voters}_{args.news_file}_{args.use_news_agent}_{expname}.json"

        if survey == "Reddit.Big5":
            os.system(
                f"python src/election_sim/config_utils/gen_config.py "
                f"--exp_name {args.voters} "
                f"--survey {survey} "
                f"--cfg_name {config_name} "
                f"--num_agents {N} "
                f"--reddit_json_path {ROOT_PROJ_PATH}examples/election/src/election_sim/sim_utils/reddit_personas/reddit_agents.json"
                f" --use_news_agent {args.use_news_agent} --news_file {args.news_file}"  # NA
            )
        else:
            os.system(
                f"python examples/election/src/election_sim/config_utils/gen_config.py --exp_name {args.voters} --survey {survey} --cfg_name {config_name}  --num_agents {N}"
                + f" --use_news_agent {args.use_news_agent} --news_file {args.news_file}"  # NA
            )

    # external objects
    model = select_large_language_model(
        args.outdir + config_name + "prompts_and_responses.jsonl", True
    )
    embedder = get_sentance_encoder()
    with open(config_name) as file:
        config_data = json.load(file)

    with open(config_data["evals_config_filename"]) as file:
        eval_config_data = json.load(file)

    print([agent["name"] for agent in config_data["agents"]])

    # rootname  for all output files (note that if config is loaded, this overwrites the location)
    config_data["output_rootname"] = args.outdir + config_data["agent_config_filename"]

    # Add sim parameters to config for saving
    config_data.update(vars(args))

    # write config file by default in outdir
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)
    elif os.path.exists(config_data["output_rootname"]):
        sys.exit("output files for this setting already exist!")
    with open(config_data["output_rootname"], "w") as outfile:
        json.dump(config_data, outfile, indent=4)
    with open(
        config_data["output_rootname"].split(".")[0]
        + "_"
        + config_data["evals_config_filename"]
        + ".json",
        "w",
    ) as outfile:
        json.dump(eval_config_data, outfile, indent=4)

    if USE_MASTODON_SERVER:
        clear_mastodon_server(len(config_data["agents"]) + int(len(args.use_news_agent) > 0))

    # simulation parameter inputs
    episode_length = args.T
    shared_memories = (
        config_data["shared_memories_template"]
        + [
            config_data["candidate_info"][p]["policy_proposals"]
            for p in list(config_data["candidate_info"].keys())
        ]
        + [config_data["mastodon_usage_instructions"]]
    )

    run_sim(
        model,
        embedder,
        config_data["agents"],
        shared_memories,
        config_data["mastodon_usage_instructions"],
        # NA add the news agent, if not used in the simulation, it will be None
        config_data["news_agents"],
        config_data["custom_call_to_action"],
        config_data["candidate_info"],
        eval_config_data,
        episode_length,
        config_data["output_rootname"].split(".")[0] + "_output.jsonl",
    )
