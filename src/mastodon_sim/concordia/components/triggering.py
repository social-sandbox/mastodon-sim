# Copyright 2023 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""A component that runs the phone scene when a phone action is detected."""

from collections.abc import Sequence
from typing import Literal

from concordia.agents import deprecated_agent, entity_agent_with_logging
from concordia.associative_memory import associative_memory, blank_memories
from concordia.clocks import game_clock
from concordia.document import interactive_document
from concordia.language_model import language_model
from concordia.typing import component
from concordia.utils import helper_functions

from mastodon_sim.concordia.components import apps, logging, scene


class SceneTriggeringComponent(component.Component):
    """Runs the phone scene when a phone action is detected."""

    def __init__(  # noqa: PLR0913
        self,
        players: Sequence[entity_agent_with_logging.EntityAgentWithLogging],
        phones: Sequence[apps.Phone],
        model: language_model.LanguageModel,
        memory: associative_memory.AssociativeMemory,
        clock: game_clock.MultiIntervalClock,
        memory_factory: blank_memories.MemoryFactory,
        log_color: Literal[
            "black",
            "grey",
            "red",
            "green",
            "yellow",
            "blue",
            "magenta",
            "cyan",
            "light_grey",
            "dark_grey",
            "light_red",
            "light_green",
            "light_yellow",
            "light_blue",
            "light_magenta",
            "light_cyan",
            "white",
        ]
        | None = "magenta",
        verbose: bool = False,
        semi_verbose: bool = True,
    ):
        self._players = players
        self._phones = phones
        self._model = model
        self._clock = clock
        self._memory_factory = memory_factory
        self._memory = memory
        self._logger = logging.Logger(log_color, verbose, semi_verbose)

    def name(self):  # noqa: D102
        return "State of phone"

    def _is_phone_event(self, event_statement: str) -> bool:
        document = interactive_document.InteractiveDocument(self._model)
        document.statement(f"Event: {event_statement}")

        return document.yes_no_question(
            "Did a player engage in or prepare/plan to engage in any activity typically associated"
            " with smartphone use during this event? Consider not only explicit mentions"
            " of phone interaction, but also actions commonly performed using"
            " mobile apps or smartphone features, as well as preparations or plans to do so. Riverbend.social is a social media platform, so any mentions of it will likely involve phone use."
        )

    def _get_player_from_event(self, event_statement: str) -> deprecated_agent.BasicAgent | None:
        document = interactive_document.InteractiveDocument(self._model)
        document.statement(
            f"Event: {event_statement}. This event states that someone interacted"
            " with their phone."
        )

        for player in self._players:
            is_player_using_phone = helper_functions.filter_copy_as_statement(
                document
            ).yes_no_question(
                f"""
                Is {player.name} the main subject performing the action in this event? Only choose yes if {player.name} is explicitly mentioned?
                """
            )

            if is_player_using_phone:
                return player

        return None

    def _get_phone(self, player_name: str) -> apps.Phone:
        return next(p for p in self._phones if p.player_name == player_name)

    def _get_player_using_phone(self, event_statement: str) -> deprecated_agent.BasicAgent | None:
        self._logger.semi_verbose("Checking if the phone was used...")

        if not self._is_phone_event(event_statement):
            self._logger.semi_verbose("The phone was not used.")
            return None

        player = self._get_player_from_event(event_statement)

        if player is None:
            self._logger.semi_verbose("The phone was not used.")
        else:
            self._logger.semi_verbose(f"Player using the phone: {player.name}")
        return player

    def _run_phone_scene(self, player: deprecated_agent.BasicAgent):
        print("Starting phone scene")
        phone_scene = scene.build(
            player,
            self._get_phone(player.name),
            clock=self._clock,
            model=self._model,
            memory_factory=self._memory_factory,
        )
        print("Built phone scene")
        with self._clock.higher_gear():
            scene_output = phone_scene.run_episode()

        for event in scene_output:
            player.observe(event)
            self._memory.add(event)
        return scene_output

    def update_after_event(self, event_statement: str):  # noqa: D102
        player = self._get_player_using_phone(event_statement)
        if player is not None:
            self._run_phone_scene(player)

    def partial_state(self, player_name: str):  # noqa: D102
        return self._get_phone(player_name).description()
