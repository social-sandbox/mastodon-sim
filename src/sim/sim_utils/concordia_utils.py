import importlib

from concordia.associative_memory import (
    associative_memory,
    blank_memories,
    formative_memories,
    importance_function,
)


def generate_concordia_memory_objects(
    model, embedder, shared_agent_memories, gamemaster_memories, clock
):
    importance_model = importance_function.ConstantImportanceModel()
    importance_model_gm = importance_function.ConstantImportanceModel()

    blank_memory_factory = blank_memories.MemoryFactory(
        model=model,
        embedder=embedder,
        importance=importance_model.importance,
        clock_now=clock.now,
    )
    formative_memory_factory = formative_memories.FormativeMemoryFactory(
        model=model,
        shared_memories=shared_agent_memories,
        blank_memory_factory_call=blank_memory_factory.make_blank_memory,
    )

    game_master_memory = associative_memory.AssociativeMemory(
        embedder, importance_model_gm.importance, clock=clock.now
    )
    for memory in gamemaster_memories:
        game_master_memory.add(memory)

    return (
        importance_model,
        importance_model_gm,
        blank_memory_factory,
        formative_memory_factory,
        game_master_memory,
    )


def make_profiles(agent_data):
    # Create agents from JSON data and classify them
    roles = {}
    profiles = {}
    for agent_info in agent_data:
        roles[agent_info["name"]] = agent_info["role_dict"]["name"]
        profiles[agent_info["name"]] = {}
        profiles[agent_info["name"]]["role_dict"] = agent_info["role_dict"] | {
            "agent_name": agent_info["name"]
        }
        profiles[agent_info["name"]]["cfg"] = (
            agent_info["posts"]
            if agent_info["role_dict"]["name"] == "exogenous"
            else formative_memories.AgentConfig(
                name=agent_info["name"],
                gender=agent_info["gender"],
                goal=agent_info["goal"],
                context=agent_info["context"],
                traits=agent_info["traits"],
            )
        )

    return profiles, roles


def build_agent_with_memories(obj_args, profile_item):
    profile_cfg = profile_item["cfg"]
    role_dict = profile_item["role_dict"]
    (formative_memory_factory, model, clock, time_step, setting_info) = obj_args

    # for non-exogenous agents
    if role_dict["name"] == "exogenous":
        module_path = "agent_utils.exogenous_agent"
        input_args = {"posts": profile_cfg, "name": role_dict["agent_name"]}
        store_for_local_post_analysis = None
    else:
        setting_data = {
            "setting_details": setting_info["details"],
            "setting_description": setting_info["description"],
        }
        module_path = "sim_setting." + role_dict["module_path"]
        mem = formative_memory_factory.make_memories(profile_cfg)
        input_args = {
            "config": profile_cfg,
            "input_data": role_dict | setting_data,
            "model": model,
            "clock": clock,
            "update_time_interval": time_step,
            "memory": mem,
        }
        store_for_local_post_analysis = mem

    agent_module = importlib.import_module(module_path)
    agent = agent_module.AgentBuilder.build(**input_args)
    return agent, store_for_local_post_analysis
