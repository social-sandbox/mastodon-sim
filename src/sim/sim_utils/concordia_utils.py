import importlib
import json

from concordia.agents import entity_agent_with_logging
from concordia.associative_memory import (
    associative_memory,
    blank_memories,
    formative_memories,
    importance_function,
)
from concordia.typing import entity_component


def save_to_json(
    agent: entity_agent_with_logging.EntityAgentWithLogging,
) -> str:
    """Saves an agent to JSON data.

    This function saves the agent's state to a JSON string, which can be loaded
    afterwards with `rebuild_from_json`. The JSON data
    includes the state of the agent's context components, act component, memory,
    agent name and the initial config. The clock, model and embedder are not
    saved and will have to be provided when the agent is rebuilt. The agent must
    be in the `READY` phase to be saved.

    Args:
      agent: The agent to save.

    Returns
    -------
      A JSON string representing the agent's state.

    Raises
    ------
      ValueError: If the agent is not in the READY phase.
    """
    if agent.get_phase() != entity_component.Phase.READY:
        raise ValueError("The agent must be in the `READY` phase to be saved.")

    data = {
        component_name: agent.get_component(component_name).get_state()
        for component_name in agent.get_all_context_components()
    }

    data["act_component"] = agent.get_act_component().get_state()

    config = agent.get_config()
    if config is not None:
        data["agent_config"] = config.to_dict()

    return json.dumps(data)


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
    (formative_memory_factory, model, clock, time_step, setting_info, mastodon_apps) = obj_args

    if role_dict["name"] != "exogenous":
        mem = formative_memory_factory.make_memories(profile_cfg)

        role_and_setting_config = {
            "role_details": role_dict,
            "agent_name": role_dict["agent_name"],
            "setting_details": setting_info["details"],
            "setting_description": setting_info["description"],
        }

        agent_module = importlib.import_module("sim_setting.agent_lib." + role_dict["class"])
        if not hasattr(agent_module, "Agent"):
            raise AttributeError("No 'Agent' class found.")

        agent = agent_module.Agent.build(
            config=profile_cfg,
            model=model,
            clock=clock,
            update_time_interval=time_step,
            memory=mem,
            role_and_setting_config=role_and_setting_config,
        )
    else:
        mem = ""
        agent_module = importlib.import_module("agent_utils." + role_dict["class"])
        agent = agent_module.Agent(
            name=role_dict["agent_name"],
            app=mastodon_apps[role_dict["agent_name"]],
            posts=profile_cfg,
        )
    return agent, mem
