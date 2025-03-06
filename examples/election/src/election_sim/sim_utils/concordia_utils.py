import os
import sys

from concordia.associative_memory import (
    associative_memory,
    blank_memories,
    formative_memories,
    importance_function,
)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

import importlib
import json

from concordia.agents import entity_agent_with_logging
from concordia.typing import entity_component


class AgentLoader:
    def __init__(self):
        self.agent_classes = {}  # Stores agent classes

    def load_agent_class(self, key, module_name):
        """
        Dynamically loads an Agent class from a module inside 'scenario_agents' package.
        Example: module_name = 'candidate' will load scenario_agents.candidate.Agent
        """
        try:
            full_module_name = f"scenario_agents.{module_name}"
            module = importlib.import_module(full_module_name)

            # Ensure the module has an 'Agent' class
            if not hasattr(module, "Agent"):
                raise AttributeError(f"No 'Agent' class found in '{full_module_name}'.")

            # Store the class (not an instance yet)
            self.agent_classes[key] = module.Agent
            print(f"Successfully loaded class '{key}' from '{full_module_name}'.")

        except Exception as e:
            print(f"Error loading agent class '{key}': {e}")


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


def init_concordia_objects(model, embedder, shared_memories, clock):
    # shared_context = model.sample_text(  # TODO: deprecated?
    #     "Summarize the following passage in a concise and insightful fashion. "
    #     + "Make sure to include information about Mastodon:\n"
    #     + "\n".join(shared_memories)
    #     + "\nSummary:",
    #     max_tokens=2048,
    # )
    # print(shared_context)

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
        shared_memories=shared_memories,
        blank_memory_factory_call=blank_memory_factory.make_blank_memory,
    )

    game_master_memory = associative_memory.AssociativeMemory(
        embedder, importance_model_gm.importance, clock=clock.now
    )

    return (
        importance_model,
        importance_model_gm,
        blank_memory_factory,
        formative_memory_factory,
        game_master_memory,
    )


def make_profiles(agent_data):
    # Create agents from JSON data and classify them
    agent_profiles = []

    for agent_info in agent_data:
        agent_profiles.append(
            (
                formative_memories.AgentConfig(
                    name=agent_info["name"],
                    gender=agent_info["gender"],
                    goal=agent_info["goal"],
                    context=agent_info["context"],
                    traits=agent_info["traits"],
                ),
                agent_info["role"] | {"player_name": agent_info["name"]},
            )
        )
    return agent_profiles


def build_agent_with_memories(obj_args, profile_item):
    (profile, role) = profile_item
    (formative_memory_factory, model, clock, time_step, setting_info, map_data) = obj_args
    loader = AgentLoader()
    # Load classes
    for key, module in map_data.items():
        loader.load_agent_class(key, module)
    mem = formative_memory_factory.make_memories(profile)

    role_and_setting_config = {
        "role_details": role,
        "agent_name": role["player_name"],
        "setting_details": setting_info["details"],
        "setting_description": setting_info["description"],
    }
    agent = loader.agent_classes[role["name"]].build(
        config=profile,
        model=model,
        clock=clock,
        update_time_interval=time_step,
        memory=mem,
        role_and_setting_config=role_and_setting_config,
    )

    return agent, mem
