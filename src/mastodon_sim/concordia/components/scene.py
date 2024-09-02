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

"""A GameMaster that simulates a player's interaction with their phone."""

import re
import textwrap
from html import unescape
from typing import Literal

import termcolor
from concordia.agents import basic_agent
from concordia.associative_memory import blank_memories
from concordia.clocks import game_clock
from concordia.document import interactive_document
from concordia.environment import game_master as game_master_lib
from concordia.language_model import language_model
from concordia.thought_chains import thought_chains
from concordia.typing import agent, component
from concordia.typing.entity import OutputType

from mastodon_sim import mastodon_ops
from mastodon_sim.concordia.components import apps, logging
from mastodon_sim.concordia.components.apps import COLOR_TYPE

# _PHONE_CALL_TO_ACTION = textwrap.dedent("""\
#   What action is {name} currently performing or has just performed
#   with their smartphone to best achieve their goal?
#   Consider their plan, but deviate if necessary.
#   Give a specific activity using one app. For example:
#   {name} uses/used the Chat app to send "hi, what's up?" to George.
#   """)

import time
import functools

def timed_function(tag="general"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time
            with open("time_logger.txt", "a") as f:
                f.write(f"{tag} - {func.__name__} took {duration:.6f}s on {time.asctime()}\n")
            return result
        return wrapper
    return decorator

_PHONE_CALL_TO_ACTION = textwrap.dedent("""\
    Based on {name}'s current goal and recent observations, what specific action would they likely perform on their phone right now, and what information would they need to perform it?

    Guidelines:
    1. Choose a single, specific action that can be performed using one app. There should be a single clear action.
    2. The action should align with {name}'s plan, but deviate if a more suitable option presents itself.
    3. Ensure the action is contextually appropriate, considering recent observations.
    4. Provide a detailed description of the exact action, including the app used and important context such as Toot IDs.

    Examples of contextually appropriate actions:
    - Using the Mastodon app to read their feed: {name} opens the Mastodon app and reads their feed.
    - Posting a toot: {name} opens the Mastodon app and posts a toot. You can tag other users by adding '@' before mentioning their username.
    - Checking Mastodon notifications: "{name} reads their Mastodon notifications"
    - Liking a Mastodon post: {name} likes a post they have recently read with a given Toot ID. (Return toot ID of the post you want to like)
    - Replying to a Mastodon post: {name} replies to a post they have recently read with a given Toot ID.
    - Using the Mastodon app to send a message: {name} opens the Mastodon app and send a direct message to George.

    Remember:
    - Consider current observations so as not to repeat actions that have already been performed.
    - Certain actions require prior knowledge (e.g., liking or replying to a specific post) which would require reading that information recently
    - Don't suggest reading notifications or feeds if they've already been checked recently.
    - Consider the time of day and the agent's current situation when suggesting actions.
    - Ensure responses to other toots are done using the Toot Response feature and not in a new toot
    - If the action is a post or message, a direct quote of that post or message should be included.
    - If reading from a timeline or notifications, just state that — don't fabricate what has been read.
                                        
    Note: Carefully look at most recent observations so as to not repeat any actions. Ensure you never repeat what you have already posted.
    {name} should like a toot if they agree with it.
    {name} should tag other users if referring to them.
  """)


_PHONE_ACTION_SPEC = agent.ActionSpec(_PHONE_CALL_TO_ACTION, OutputType.FREE, tag="phone")


def build(
    player: basic_agent.BasicAgent,
    phone: apps.Phone,
    clock: game_clock.MultiIntervalClock,
    model: language_model.LanguageModel,
    memory_factory: blank_memories.MemoryFactory,
) -> game_master_lib.GameMaster:
    """Build a GameMaster that simulates a player's interaction with their phone.

    Args:
      player: The player who is interacting with the phone.
      phone: The player's phone.
      clock: A clock.
      model: A language model.
      memory_factory: A memory factory for creating the GM's memory.

    Returns
    -------
    concordia.environment.game_master.GameMaster
      A GameMaster that simulates a player's interaction with their phone
    """
    memory = memory_factory.make_blank_memory()
    phone_component = _PhoneComponent(model, player, phone)
    # reflectionx = 
    return game_master_lib.GameMaster(
        model=model,
        memory=memory,
        clock=clock,
        name="PhoneGameMaster",
        players=(player,),
        components=(phone_component,),
        action_spec=_PHONE_ACTION_SPEC,
        update_thought_chain=(thought_chains.identity,),
        player_observes_event=False,
    )


class _PhoneComponent(component.Component):
    """Parses the player's actions and invokes them on phone apps."""

    def __init__(  # noqa: PLR0913
        self,
        model: language_model.LanguageModel,
        player: basic_agent.BasicAgent,
        phone: apps.Phone,
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
        | None = "yellow",
        verbose: bool = True,
        semi_verbose: bool = False,
    ):
        self._model = model
        self._player = player
        self._phone = phone
        self._logger = logging.Logger(log_color, verbose, semi_verbose)
        self._state = ""

    def name(self) -> str:
        return "PhoneComponent"

    def _print(
        self,
        entry: str,
        emoji: str = "",
        color: COLOR_TYPE = None,
    ) -> None:
        formatted_entry = f"{emoji} {entry}" if emoji else entry
        print(termcolor.colored(formatted_entry, color or self._log_color))

    def terminate_episode(self) -> bool:
        chain_of_thought = interactive_document.InteractiveDocument(self._model)
        chain_of_thought.statement(f"Interaction with phone:\n{self._state}")
        did_conclude = chain_of_thought.yes_no_question(
            "Has the user achieved their goal with their phone or are they still"
            " actively in the process of completing a phone task?"
        )
        return did_conclude

    @timed_function(tag="update_phonegamemaster")
    def update_after_event(self, event_statement: str):
        # print(f"Player state:\n{self._player.state()}")
        # TODO: May want to add player state to the transcript
        print("Inside phone_update_after_event")
        self._state += "\n" + event_statement.strip()
        chain_of_thought = interactive_document.InteractiveDocument(self._model)
        chain_of_thought.statement(event_statement)
        chain_of_thought.statement(self._phone.description())
        app_index = chain_of_thought.multiple_choice_question(
            "In the above transcript, what app did the user use?",
            answers=self._phone.app_names(),
        )
        app = self._phone.apps[app_index]
        action_names = [a.name for a in app.actions()]
        chain_of_thought.statement(app.description())
        action_index = chain_of_thought.multiple_choice_question(
            "In the above transcript, what action did the user perform?",
            answers=action_names,
        )
        print(action_index)
        toot_id_required = chain_of_thought.yes_no_question(
            "In the above transcript, does the user's action require a numeric toot id? (numeric toot id is required for replying, liking etc.)"
        )
        print(toot_id_required)
        if toot_id_required:
            # find most recent statement
            print("Processing Toot IDx")
            p_username = app.public_get_username(self._player.name)
            print(p_username)
            timeline = mastodon_ops.get_own_timeline(
                p_username, limit=10
            )
            print("Got ID from Mastodon")
            def _clean_html(html_string):
                clean_text = re.sub("<[^<]+?>", "", unescape(html_string))
                return re.sub(r"\s+", " ", clean_text).strip()

            output = []
            for post in timeline:
                output.append(
                    f"User: {post['account']['display_name']} (@{post['account']['username']}), Content: {_clean_html(post['content'])}, Toot ID: {post['id']}"
                )
            if len(output) > 0:
                toot_index = chain_of_thought.multiple_choice_question(
                    "In the above transcript, which of the following toots is the user liking or responding to? Identify this using the name (if mentioned) and the context of the action and the toots from the timeline below",
                    answers=output,
                )
                responding_id = output[toot_index].split("Toot ID: ")[1]
                chain_of_thought.statement(
                    f"The exact Toot ID called for in the above action is: {responding_id}\n"
                )
                print(responding_id)
        print("Continuing action!")
        action = app.actions()[action_index]

        try:
            argument_text = chain_of_thought.open_question(
                action.instructions(),
                terminators=[],
                # Roughly, Mastodon has 500 char limit -> 125 tokens + 100 tokens for other params
                max_tokens=500 // 4 + 100,
                # print_prompt=True,  # TODO: add this arg to the open_question method
            )
            self._print(
                f"Attempting to invoke action '{action.name}'"
                f" with the argument_text:\n{argument_text}",
                color="yellow",
            )
            result = app.invoke_action(action, argument_text)

            # TODO: verify if this makes sense
            if isinstance(result, str):
                try:
                    self._player.observe(result)
                    self._print("Phone action result observed.", color="yellow")
                except Exception as e:
                    self._print(f"Error while observing result: {e}", color="red")

            return [result]
        except apps.ActionArgumentError:
            return []
        except Exception as e:
            self._print("Error while invoking action: " + str(e), color="red")
            return []
