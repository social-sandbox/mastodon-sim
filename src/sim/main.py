import concurrent.futures
import datetime
import importlib
import logging
import os
import random
import sys
import time
import warnings
from functools import partial
from pathlib import Path

import yaml
from dotenv import load_dotenv
from omegaconf import OmegaConf

with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    import sentence_transformers

from concordia import __file__ as concordia_location

print(f"importing Concordia from: {concordia_location}")

# concordia functions
from concordia.clocks import game_clock
from concordia.typing.entity import ActionSpec, OutputType

# sim functions
from sim_utils import media_utils
from sim_utils.agent_speech_utils import (
    deploy_surveys,
    write_seed_toot,
)
from sim_utils.concordia_utils import (
    build_agent_with_memories,
    generate_concordia_memory_objects,
    make_profiles,
)
from sim_utils.misc_sim_utils import event_logger

# mastodon_sim functions
from mastodon_sim.concordia import apps
from mastodon_sim.mastodon_ops import check_env, get_public_timeline, reset_users, update_bio
from mastodon_sim.mastodon_utils import get_users_from_env

# Go up two levels to set current working directory to project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
print("project root: " + str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

SIM_EXAMPLE = "election"
sys.path.insert(0, str(PROJECT_ROOT / "examples" / SIM_EXAMPLE))

# example functions
from gen_config import generate_output_configs


def clear_mastodon_server(max_num_agents):
    users = get_users_from_env()[: max_num_agents + 1]
    reset_users(users, skip_confirm=True, parallel=True)
    if len(get_public_timeline(limit=None)):
        print("All posts not cleared. Running reset operation again...")
        reset_users(users, skip_confirm=True, parallel=True)
    else:
        print("All posts cleared")


def select_large_language_model(model_name, log_file, debug_mode):
    if "sonnet" in model_name:
        GPT_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        model = amazon_bedrock_model.AmazonBedrockLanguageModel(
            # -            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0"
            model_id="claude-3-5-sonnet-latest"  # "anthropic.claude-3-5-sonnet-20240620-v1:0"
        )

    elif "gpt" in model_name:
        GPT_API_KEY = os.getenv("OPENAI_API_KEY")
        if not GPT_API_KEY:
            raise ValueError("GPT_API_KEY is required.")
        model = media_utils.GptLanguageModel(
            api_key=GPT_API_KEY, model_name=model_name, log_file=log_file, debug=debug_mode
        )
    else:
        raise ValueError("Unknown model name.")
    return model


def get_sentance_encoder(model_name):
    # Setup sentence encoder
    st_model = sentence_transformers.SentenceTransformer(model_name)
    embedder = lambda x: st_model.encode(x, show_progress_bar=False)
    return embedder


# def add_news_agent_to_mastodon_app(
#     news_agent, action_logger, agents, mastodon_apps, app_description, use_server
# ):
#     user_mapping = mastodon_apps[agents[0].name].get_user_mapping()
#     for i, n_agent in enumerate(news_agent):
#         mastodon_apps[n_agent["name"]] = apps.MastodonSocialNetworkApp(
#             action_logger=action_logger,
#             perform_operations=use_server,
#             app_description=app_description,
#         )
#         user_mapping[n_agent["mastodon_username"]] = f"user{len(agents) + 1 + i:04d}"
#         # set a mapping of display name to user name for news agent
#         mastodon_apps[n_agent["name"]].set_user_mapping(user_mapping)  # e.g., "storhampton_gazette"
#         update_bio(
#             user_mapping[n_agent["mastodon_username"]],
#             display_name=n_agent["mastodon_username"],
#             bio="Providing news reports from across Storhampton",
#         )
#         for p in agents:
#             mastodon_apps[p.name].set_user_mapping(user_mapping)
#         # set followership network for the news agent
#         agent_names = [agent.name for agent in agents]
#         with concurrent.futures.ThreadPoolExecutor() as executor:
#             futures = []
#             for follower in agent_names:
#                 print(follower)
#                 # Ensure every user, follows the news agent
#                 if (
#                     follower != n_agent["name"]
#                 ):  # this actually never possible because news agent is not in agents but I added as just in case argument
#                     futures.append(
#                         executor.submit(
#                             mastodon_apps[follower].follow_user,
#                             follower,
#                             n_agent["mastodon_username"],
#                         )
#                     )
#             # Optionally, wait for all tasks to complete
#             for future in concurrent.futures.as_completed(futures):
#                 try:
#                     future.result()  # This will raise any exceptions that occurred during execution, if any
#                 except Exception as e:
#                     print(f"Ignoring already-following error: {e}")


def set_up_mastodon_app_usage(roles, role_parameters, action_logger, app_description, use_server):
    active_rates = {}
    for agent_name, role in roles.items():
        active_rates[agent_name] = role_parameters["active_rates_per_episode"][role]

    mastodon_apps = {
        agent_name: apps.MastodonSocialNetworkApp(
            action_logger=action_logger,
            perform_operations=use_server,
            app_description=app_description,
        )
        for agent_name in roles
    }
    user_mapping = {agent_name.split()[0]: f"user{i + 1:04d}" for i, agent_name in enumerate(roles)}
    for p in mastodon_apps:
        mastodon_apps[p].set_user_mapping(user_mapping)

    # initiailize initial social network
    # Pre-generate unique follow relationships
    follow_pairs = set()
    # Now, generate additional follow relationships between agents.
    role_prob_matrix = role_parameters["initial_follow_prob"]
    agent_roles = []
    for agent_i, role_i in roles.items():
        for agent_j, role_j in roles.items():
            prob = role_prob_matrix[role_i][role_j]
            # if follower != followee:
            #     # With a 20% chance, create mutual follow relationships.
            #     if random.random() < 0.2:
            #         follow_pairs.add((follower, followee))
            #         follow_pairs.add((followee, follower))
            #     # Otherwise, with a create a one-direction follow according to stored probability.
            if random.random() < prob:
                follow_pairs.add((agent_i, agent_j))

    # Execute the follow operations concurrently.
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for follower, followee in follow_pairs:
            # Submit the follow operation from the appropriate mastodon app instance.
            futures.append(executor.submit(mastodon_apps[follower].follow_user, follower, followee))

    # Wait for all tasks to complete, handling exceptions as needed.
    for future in concurrent.futures.as_completed(futures):
        try:
            future.result()
        except Exception as e:
            # If a follow error occurs (e.g. already following), we simply log and ignore it.
            print(f"Ignoring error: {e}")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                update_bio, user_mapping[agent_name], display_name=agent_name, bio=""
            )  # update with generated bios?
            for agent_name in user_mapping
        ]
    # Optionally, wait for all tasks to complete
    for future in concurrent.futures.as_completed(futures):
        future.result()  # This will raise any exceptions that occurred during execution, if any

    phones = {
        agent_name: apps.Phone(agent_name, apps=[mastodon_apps[agent_name]])
        for agent_name, role in roles.items()
        if role != "exogenous"
    }

    return mastodon_apps, phones, active_rates


def post_seed_toots(agents, mastodon_apps):
    # Parallelize the loop using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit tasks for each agent
        futures = [
            executor.submit(
                lambda agent=agent: (
                    mastodon_apps[agent._agent_name].post_toot(
                        agent._agent_name, status=agent.seed_toot
                    )
                    if hasattr(agent, "seed_toot")
                    else mastodon_apps[agent._agent_name].post_toot(
                        agent._agent_name, status=write_seed_toot(agent)
                    )
                )
            )
            for agent in agents
        ]

        # Optionally, wait for all tasks to complete
        for future in concurrent.futures.as_completed(futures):
            future.result()  # This will raise any exceptions that occurred in the thread, if any


def get_active_agents(active_rates):
    # random model of realworld agent lives (so that going online every delta is a poisson point process)
    # (active_rate could be a agent engagement component that could be based on a time-varying rate process updated at each episode according to response about how engaged agent is feeling)
    active_agents = []
    for agent_name, rate in active_rates.items():
        if random.random() < rate:
            active_agents.append(agent_name)
    return active_agents


def run_sim(
    model,
    embedder,
    agent_settings,
    gamemaster_settings,
    app_description,
    custom_call_to_action,
    setting_info,
    probe_config,
    num_episodes,
    output_rootname,
    use_server,
    output_post_analysis=False,
):
    time_step = datetime.timedelta(minutes=30)
    today = datetime.date.today()
    SETUP_TIME = datetime.datetime(year=today.year, month=today.month, day=today.day, hour=8)  # noqa: DTZ001
    START_TIME = datetime.datetime(year=today.year, month=today.month, day=today.day, hour=8)  # noqa: DTZ001
    clock = game_clock.MultiIntervalClock(
        start=SETUP_TIME, step_sizes=[time_step, datetime.timedelta(seconds=10)]
    )

    # build agent models
    agent_data = agent_settings["directory"]
    get_idx = lambda name: [ait for ait, agentt in enumerate(agent_data) if agentt["name"] == name][
        0
    ]

    profiles, roles = make_profiles(agent_data)  # profile format: (agent_config,role)
    role_parameters = setting_info["details"]["role_parameters"]

    (
        importance_model,
        importance_model_gm,
        blank_memory_factory,
        formative_memory_factory,
        gamemaster_memory,
    ) = generate_concordia_memory_objects(
        model,
        embedder,
        agent_settings["shared_memories"],
        gamemaster_settings["gamemaster_memories"],
        clock,
    )

    action_event_logger = event_logger("action", output_rootname + "_event_output.jsonl")
    action_event_logger.episode_idx = -1
    mastodon_apps, phones, active_rates = set_up_mastodon_app_usage(
        roles, role_parameters, action_event_logger, app_description, use_server
    )

    agents = []
    memories = {}
    obj_args = (formative_memory_factory, model, clock, time_step, setting_info, mastodon_apps)
    build_agent_with_memories_part = partial(build_agent_with_memories, obj_args)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(profiles)) as pool:
        for agent_obj in pool.map(build_agent_with_memories_part, profiles.values()):
            agent, mem = agent_obj
            agents.append(agent)
            memories[agent._agent_name] = mem
    for agent in agents:
        if roles[agent._agent_name] == "exogenous":
            agent.seed_toot = agent_data[get_idx(agent._agent_name)]["seed_toot"]
            for post_text in agent.posts:
                agent.posts[post_text] = [
                    str(PROJECT_ROOT) + "/" + path for path in agent.posts[post_text]
                ]
        else:
            for observation in agent_settings["initial_observations"]:
                agent.observe(observation.format(name=agent._agent_name))
    post_seed_toots(agents, mastodon_apps)

    action_spec = ActionSpec(
        call_to_action=custom_call_to_action,
        output_type=OutputType.FREE,
        tag="action",
    )

    # Experimental version (custom call to action and thought chains)
    gamemaster_module = importlib.import_module(
        "agent_utils." + gamemaster_settings["online_gamemaster"]
    )
    env = gamemaster_module.GameMaster(
        model=model,
        memory=gamemaster_memory,
        phones=phones,
        clock=clock,
        agents=agents,
        roles=roles,
        action_spec=action_spec,
        memory_factory=blank_memory_factory,
        embedder=embedder,
        importance_model=importance_model,
        importance_model_gm=importance_model_gm,
    )

    # initialize
    eval_event_logger = event_logger("eval", output_rootname + "_event_output.jsonl")
    eval_event_logger.episode_idx = -1

    # main loop
    start_time = time.time()  # Start timing
    model.agent_names = [
        agent._agent_name for agent in agents
    ]  # needed for tagging names to thoughts
    for i in range(num_episodes):
        print(f"Episode: {i}. Deploying survey...", end="")
        eval_event_logger.episode_idx = i
        action_event_logger.episode_idx = i
        model.meta_data["episode_idx"] = i
        # for agent in agents:
        #     agent_dir = os.path.join("output/agent_checkpoints", agent._agent_name)
        #     os.makedirs(agent_dir, exist_ok=True)
        #     file_path = os.path.join(agent_dir, f"Episode_{i}.json")
        # Get JSON data from agent
        # json_data = save_to_json(agent)
        # with open(file_path, "w") as file:
        #     file.write(json.dumps(json_data, indent=4))
        deploy_surveys(
            [agent for agent in agents if roles[agent._agent_name] != "exogenous"],
            probe_config,
            eval_event_logger,
        )
        print("complete")

        active_agent_names = get_active_agents(active_rates)

        if len(active_agent_names) == 0:
            clock.advance()
        else:
            start_timex = time.time()

            env.step(active_agents=active_agent_names)
            end_timex = time.time()
            with open(
                output_rootname + "time_logger.txt",
                "a",
            ) as f:
                f.write(
                    f"Episode with {len(active_agent_names)} finished - took {end_timex - start_timex}\n"
                )
    if output_post_analysis:
        post_analysis(env, model, agents, memories, output_rootname)

    #################################################################


def generate_default_settings():
    default_sim_settings = {}
    default_sim_settings["seed"] = 1  # seed used for python's random module"
    default_sim_settings["num_agents"] = 20  # number of agents
    default_sim_settings["num_episodes"] = 1  # number of episodes
    default_sim_settings["use_server"] = (
        True  # server (e.g. www.social-sandbox.com, www.socialsandbox2.com)
    )
    default_sim_settings["use_news_agent"] = (
        "with_images"  # use news agent in the simulation 'with_images', else without
    )
    default_sim_settings["sentence_encoder"] = (
        "sentence-transformers/all-mpnet-base-v2"  # select sentence embedding model
    )
    default_sim_settings["model"] = "gpt-4o-mini"  # select language model to run sim
    default_sim_settings["persona_type"] = "Reddit.Big5"  # persona
    default_sim_settings["run_name"] = "run1"  # experiment label
    default_sim_settings["platform"] = "Mastodon"
    default_sim_settings["gamemasters"] = {
        "online_gamemaster": "app_side_only_gamemaster",
        "reallife_gamemaster": None,
    }
    with open("conf/sim/default.yaml", "w") as outfile:
        yaml.dump(default_sim_settings, outfile, default_flow_style=False)
    return default_sim_settings


def generate_config(cfg):
    soc_sys_settings, probes, agents = generate_output_configs(cfg)

    # make output storage directory
    outdir = Path(f"examples/{SIM_EXAMPLE}/output")
    outdir.mkdir(exist_ok=True)
    config_name = f"N{cfg['num_agents']}_T{cfg['num_episodes']}_{cfg['persona_type'].split('.')[0]}_{cfg['persona_type'].split('.')[1]}_{soc_sys_settings['exp_name']}_{agents['inputs']['news_file']}_{cfg['use_news_agent']}_{cfg['run_name']}"
    cfg["output_rootname"] = str(outdir / config_name)
    data_config = {
        "soc_sys_settings": soc_sys_settings,
        "probes": probes,
        "agents": agents,
        "sim": cfg,
    }
    with open(cfg["output_rootname"] + ".yaml", "w") as outfile:
        yaml.dump(data_config, outfile, default_flow_style=False)

    return cfg["output_rootname"]
    # for name, cfgg in data_config.items():
    #     print("writing "+name)
    #     with open(output_rootname+'_'+name+".yaml", 'w') as outfile:
    #         yaml.dump({name:cfgg}, outfile, default_flow_style=False)
    # name = "sim"
    # with open(output_rootname+'_'+name+".yaml", 'w') as outfile:
    #     yaml.dump({name:cfg}, outfile, default_flow_style=False)

    # config = {}
    # config['defaults'] = ["_self_",{'sim': "default"}] + [
    #     config_name+"_"+name for name in data_config
    # ]
    # config['hydra'] = {}
    # config['hydra']['searchpath'] = [
    #     str(outdir.resolve()),
    # ]

    # with open("conf/" + SIM_EXAMPLE + ".yaml", 'w') as outfile:
    #     yaml.dump(config, outfile, default_flow_style=False)


def load_config(path):
    conf = OmegaConf.load(path + ".yaml")
    return conf


def configure_logging():
    # supress verbose printing of hydra's api logging so only warnings (or greater issues) are printed
    logging.getLogger("httpx").setLevel(logging.WARNING)


# @hydra.main(version_base=None, config_path="../../conf", config_name=SIM_EXAMPLE)
def main(cfg):  #: DictConfig):
    configure_logging()

    # WARNING: Make sure no one else is running a sim before setting to True since this clears the server!
    if cfg.sim.use_server:
        check_env()
    else:
        input("Sim will not use the Mastodon server. Confirm by pressing any key to continue.")

    load_dotenv(PROJECT_ROOT)

    SEED = cfg.sim.seed
    random.seed(SEED)

    # add example module to system modules as "sim_setting"
    sys.path.insert(0, str(PROJECT_ROOT / "examples"))
    package = importlib.import_module(SIM_EXAMPLE)
    sys.modules["sim_setting"] = package

    # load language models
    model = select_large_language_model(
        cfg.sim.model, cfg.sim.output_rootname + "_prompts_and_responses.jsonl", True
    )
    embedder = get_sentance_encoder(cfg.sim.sentence_encoder)

    if cfg.sim.use_server:
        clear_mastodon_server(len(cfg.agents.directory))

    # gamemaster
    gamemaster_settings = {
        "online_gamemaster": cfg.sim.gamemasters.online_gamemaster,
        "gamemaster_memories": cfg.soc_sys_settings.gamemaster_memories,
    }

    # agents
    agent_settings = {
        "directory": OmegaConf.to_container(cfg.agents.directory, resolve=True),
        "shared_memories": (
            cfg.soc_sys_settings.shared_agent_memories_template
            + [cfg.soc_sys_settings.setting_info.description]
            + [cfg.soc_sys_settings.social_media_usage_instructions]
        ),
        "initial_observations": cfg.agents.initial_observations,
    }

    run_sim(
        model,
        embedder,
        agent_settings,
        gamemaster_settings,
        cfg.soc_sys_settings.social_media_usage_instructions,
        cfg.soc_sys_settings.custom_call_to_action,
        cfg.soc_sys_settings.setting_info,
        cfg.probes,
        cfg.sim.num_episodes,
        cfg.sim.output_rootname,
        cfg.sim.use_server,
    )


if __name__ == "__main__":
    cfgg = generate_default_settings()
    output_rootname = generate_config(cfgg)
    cfg = load_config(output_rootname)
    main(cfg)
