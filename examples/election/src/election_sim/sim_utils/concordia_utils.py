import datetime
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from concordia.associative_memory import (
    associative_memory,
    blank_memories,
    formative_memories,
    importance_function,
)
from concordia.clocks import game_clock

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

import json

from concordia.agents import entity_agent_with_logging
from concordia.typing import entity_component
from scenario_agents import basic_malicious_agent, candidate_agent, voter_agent

from mastodon_sim.concordia import triggering


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
    shared_context = model.sample_text(  # TODO: deprecated?
        "Summarize the following passage in a concise and insightful fashion. "
        + "Make sure to include information about Mastodon:\n"
        + "\n".join(shared_memories)
        + "\nSummary:",
        max_tokens=2048,
    )
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


def sort_agents(agent_data):
    agent_type_names = [
        "candidate",
        "extremist",
        "moderate",
        "neutral",
        "active_voter",
        "malicious",
    ]
    ag_names = {name: [] for name in agent_type_names}
    ag_names["malicious"] = {}
    player_configs = []
    # Create agents from JSON data and classify them
    for agent_info in agent_data:
        agent = formative_memories.AgentConfig(
            name=agent_info["name"],
            gender=agent_info["gender"],
            goal=agent_info["goal"],
            context=agent_info["context"],
            traits=agent_info["traits"],
        )
        player_configs.append(agent)
        # Classify agents based on their role
        for name in agent_type_names[:-1]:
            if agent_info["role"] == name:
                ag_names[name].append(agent_info["name"])
        if agent_info["role"] == "malicious":
            ag_names["malicious"][agent_info["name"]] = agent_info["supported_candidate"]
    return ag_names, player_configs


def build_agent_with_memories(obj_args, player_config):
    (formative_memory_factory, model, clock, time_step, candidate_info, ag_names) = obj_args
    mem = formative_memory_factory.make_memories(player_config)
    print(ag_names["malicious"])
    if player_config.name in ag_names["candidate"]:
        agent = candidate_agent.build_agent(
            model=model,
            clock=clock,
            update_time_interval=time_step,
            config=player_config,
            memory=mem,
            candidate_info=candidate_info,
            ag_names=ag_names,
        )
    elif player_config.name in ag_names["malicious"]:
        agent = basic_malicious_agent.build_agent(
            model=model,
            clock=clock,
            update_time_interval=time_step,
            config=player_config,
            memory=mem,
            candidate_info=candidate_info,
            ag_names=ag_names,
        )
    else:
        agent = voter_agent.build_agent(
            model=model,
            clock=clock,
            update_time_interval=time_step,
            config=player_config,
            memory=mem,
            candidate_info=candidate_info,
            ag_names=ag_names,
        )
    return agent, mem


class SimpleGameRunner:
    """Simplified game master to run players with independent phone scene triggering in parallel."""

    def __init__(
        self,
        players,
        clock,
        action_spec,
        phones,
        model,
        memory,
        memory_factory,
        embedder,
        importance_model,
        importance_model_gm,
    ):
        """
        Args:
            players: Dictionary of players.
            clock: Game clock to advance time.
            action_spec: Action specifications for the players.
            phones: Dictionary of phones associated with each player.
            model: Language model to process events.
            memory: Shared associative memory (could be unique per player if needed).
            memory_factory: Factory to create memory instances.
        """
        self.players = {player.name: player for player in players}
        self.clock = clock
        self.action_spec = action_spec
        self.phones = phones
        self.model = model
        self.memory = memory
        self.memory_factory = memory_factory
        self.embedder = embedder
        self.importance_model = importance_model
        self.importance_model_gm = importance_model_gm
        self.player_components = self._create_player_components()
        self.log = []

    def _create_player_components(self):
        """Create a unique SceneTriggeringComponent for each player."""
        components = {}
        components = {}
        for player_name, player in self.players.items():
            memory_p = associative_memory.AssociativeMemory(
                self.embedder, self.importance_model_gm.importance, clock=self.clock.now
            )
            mem_fact = blank_memories.MemoryFactory(
                model=self.model,
                embedder=self.embedder,
                importance=self.importance_model.importance,
                clock_now=self.clock.now,
            )
            curr_clock = game_clock.MultiIntervalClock(
                self.clock.now(),
                step_sizes=[datetime.timedelta(seconds=1800), datetime.timedelta(seconds=10)],
            )
            curr_model = self.model
            components[player_name] = triggering.BasicSceneTriggeringComponent(
                player=player,
                phone=self.phones[player_name],
                model=curr_model,
                memory=memory_p,
                clock=curr_clock,
                memory_factory=mem_fact,
            )
        return components

    def _step_player(self, player):
        """Run a single player's action and trigger their phone scene."""
        try:
            # 1. Player takes action
            action = player.act(self.action_spec)
            event_statement = f"{player.name} attempted action: {action}"
            print(event_statement)
            # 2. Log the action (ensure this is thread-safe)
            self.log.append(
                {
                    "player": player.name,
                    "action": action,
                    "timestamp": self.clock.now(),
                }
            )

            # 3. Trigger the phone scene for this player using their unique component
            self.player_components[player.name].update_after_event(event_statement)

            return event_statement
        except Exception as e:
            # Handle any player-specific exceptions
            return f"Error for {player.name}: {e!s}"

    def step(self, active_players=None, timeout=300):
        """
        Run a step for the specified active players in parallel.

        Args:
            active_players: List of player names to take part in the step. If None, all players act.
            timeout: Timeout in seconds for each player's action.
        """
        if active_players is None:
            active_players = list(self.players.keys())

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._step_player, self.players[player_name.name]): player_name.name
                for player_name in active_players
            }

            try:
                # Apply an overall timeout for `as_completed`
                for future in as_completed(futures, timeout=timeout * len(active_players)):
                    player_name = futures[future]
                    try:
                        # Still applying timeout for each future result individually
                        result = future.result(timeout=timeout * 2)
                        print(f"Result for {player_name}: {result}")
                    except TimeoutError:
                        print(f"Timeout for {player_name}. Skipping their turn.")
                    except Exception as e:
                        print(f"Error in thread for {player_name}: {e!s}")
            except TimeoutError:
                # This handles the overall timeout for the entire `as_completed` call
                print("Overall step timed out before all players could complete.")

        # Advance the game clock after all players' actions are complete
        self.clock.advance()

    def run_game(self, steps=10):
        """Run the game for a given number of steps."""
        for _ in range(steps):
            self.step()  # By default, all players will act unless specified otherwise
