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
import threading

# _PHONE_CALL_TO_ACTION = textwrap.dedent("""\
#   What action is {name} currently performing or has just performed
#   with their smartphone to best achieve their goal?
#   Consider their plan, but deviate if necessary.
#   Give a specific activity using one app. For example:
#   {name} uses/used the Chat app to send "hi, what's up?" to George.
#   """)
from html import unescape
from typing import Literal

import termcolor
from concordia.agents import entity_agent_with_logging
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

file_lock = threading.Lock()

DEFAULT_CALL_TO_SPEECH = (
    "Given the above, what is {name} likely to say next? Respond in"
    ' the format `{name} -- "..."` For example, '
    'Cristina -- "Hello! Mighty fine weather today, right?", '
    'Ichabod -- "I wonder if the alfalfa is ready to harvest", or '
    'Townsfolk -- "Good morning".\n'
)

# _PHONE_CALL_TO_ACTION = textwrap.dedent("""\
#     Based on {name}'s current goal, plans and observations, what SINGLE specific action would they likely perform on their phone right now, and what information would they need to perform it?
#     Use your plan for current phone usage, tagged as [Planned Actions for upcoming Phone Usage] in your observations, alongside your previous actions to actualize the plan conducted in the current usage, tagged as [Action done on phone] to decide your next single action.
#     Mention a concrete action that can easily be converted into an API call, and don't answer with vague and general responses.

#     Guidelines:
#     1. Choose a single, specific action that can be performed using one app.
#     2. Ensure the action is contextually appropriate, considering recent observations.
#     3. Provide a detailed description of the exact action, including the app used and important context such as Toot IDs.
#     4. The action should adhere to {name}'s plans, but deviate if a more suitable option is presented.

#     Examples of contextually appropriate actions:
#     - Using the Mastodon app to read own timeline: {name} opens the Mastodon app and reads their feed.
#     - Posting a toot: {name} opens the Mastodon app and posts a toot.
#     - Checking Mastodon notifications: "{name} reads their Mastodon notifications"
#     - Liking a Mastodon post: {name} likes a post they have recently read with a given Toot ID. (Return toot ID of the post you want to like)
#     - Replying to a Mastodon post: {name} replies to a post they have recently read with a given Toot ID.
#     - Boosting a Mastodon post: {name} opens the Mastodon app to boost (Retweet) a toot - that shares it with their own followers. (Return Toot ID and the exact contents of the toot to be boosted.)
#     - Read another user's timeline: If you find a user interesting you can view their past activity and timeline (include their first name)

#     Remember:
#     - Consider current observations so as not to repeat actions that have already been performed.
#     - Certain actions require prior knowledge (e.g., liking or replying to a specific post) which would require reading that information recently
#     - Don't suggest reading notifications or feeds if they've already been checked recently.
#     - Consider the time of day and the agent's current situation when suggesting actions.
#     - Ensure responses to other toots are done using the Toot Response feature and not in a new toot
#     - If the action is a post or message, a direct quote of that post or message should be included.
#     - If reading from a timeline or notifications, just state that — don't fabricate what has been read.

#     Note: Carefully look at most recent observations so as to not repeat any actions. Ensure you never repeat what you have already posted.
#     {name} should like a toot if they agree with it.
#     {name} should boost a toot if they strongly agree with it and want people in their timeline to also see it.
#   """)
_PHONE_CALL_TO_ACTION = textwrap.dedent("""\
    Based on {name}'s current goal, plans and observations, what SINGLE specific action would they likely perform on their phone right now, and what information would they need to perform it?
    Use your plan for current phone usage, tagged as tagged as [Planned Actions for upcoming Phone Usage] in your observations, alongside your previous actiosn to actualize the plan conducted in the current usage, tagged as [Action done on phone] to decide your next single action.
    Mention a concrete action that can easily be converted into an API call, and don't answer with vague and general responses.

    Guidelines:
    1. Choose a single, specific action that can be performed using one app.
    2. Ensure the action is contextually appropriate, considering recent observations.
    3. Provide a detailed description of the exact action, including the app used and important context such as Toot IDs.
    4. The action should adhere to {name}'s plans, but deviate if a more suitable option is presented.

    Examples of contextually appropriate actions:
    - Using the Mastodon app to read own timeline: {name} opens the Mastodon app and reads their feed.
    - Posting a toot: {name} opens the Mastodon app and posts a toot.
    - Checking Mastodon notifications: "{name} reads their Mastodon notifications"
    - Liking a Mastodon post: {name} likes a post they have recently read with a given Toot ID. (Return toot ID of the post you want to like)
    - Replying to a Mastodon post: {name} replies to a post they have recently read with a given Toot ID.
    - Boosting a Mastodon post: {name} opens the Mastodon app to boost (Retweet) a toot - that shares it with their own followers. (Return Toot ID and the exact contents of the toot to be boosted.)
    - Read another user's timeline: If you find a user interesting you can view their past activity and timeline (include their first name)

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
    {name} should boost a toot if they strongly agree with it and want people in their timeline to also see it.
""")
# _PHONE_CALL_TO_ACTION = textwrap.dedent("""\
#     Based on {name}'s current goal, plans and observations, what SINGLE specific action on their phone would they likely perform now while on the storhampton.social Mastodon app, and what information would they need to perform it?

#     Here is a list of the kinds of actions to select from, and what they accomplish:
#     - Posting a toot: {name} wants to tell others something and so posts a toot.
#     - Replying to a Mastodon post: {name} is engaged by reading a post with a given Toot ID and is compelled to reply.
#     - Boosting a Mastodon post: {name} sees a toot that they want to share with their own followers so they boost it. (Return Toot ID and the exact contents of the toot to be boosted.)
#     - Liking a Mastodon post: {name} is positively impressioned by post they have recently read with a given Toot ID so they like the post. (Return toot ID of the post you want to like)

#     Guidelines:
#     1. Choose a single, specific action from the above list that can be performed on the app. Be precise and specific.
#     2. Provide a detailed description of the exact action, including the app used and important context such as Toot IDs that can easily be converted into an Mastodon API call.
#     3. For actions that require prior knowledge (e.g., liking or replying to a specific post),include that information as previously observed. Do not fabricate this information. If the action is a post or reply, a direct quote of that post or reply should be included.
#     4. Use the content of the current plan for phone usage, tagged as [Planned Actions for upcoming Phone Usage] in {name}'s recent observations above.
#     5. NEVER repeat a recently taken action (tagged as [Action done on phone] in the above), the action should have novel motivation and content, distinct from those actions already taken.
#     6. The action should adhere to {name}'s plans and, if not inconsistent with the other guidelines, be the suggested action listed above with [Suggested Action]. The action can, however, deviate if a more suitable option is presented given the engagement {name} receives.
#     7. Ensure direct responses to other toots are done using the Toot Reply action and not in a new post.
#     """)
# _PHONE_CALL_TO_ACTION = textwrap.dedent("""\
# Based on {name}'s current goal, plans and observations, what SINGLE specific action on their phone would they likely perform now while on the storhampton.social Mastodon app, and what information would they need to perform it?

# Here is a list of the valid action types to select from:
# - Posting a toot (a Mastodon post): Share new information with followers
# - Replying to a Mastodon post: Respond to a specific post using its Toot ID
# - Boosting a Mastodon post: Reshare an existing post (requires Toot ID and exact content)
# - Liking a Mastodon post: Express appreciation for a post (requires Toot ID)
# - Following a Mastodon user: adding a user in order to view their future posts (requires their user name)

# Requirements for action selection:
# 1. UNIQUENESS CONSTRAINTS:
#    - The selected action must not duplicate any previous action from the current episode (listed above by [Action done on phone])
#    - For posting/replying actions: The content must not rephrase or recreate the message of any previous post/reply
#    - For boost/like actions: Must not target any previously boosted or liked Toot IDs

# 2. ACTION SPECIFICATION:
#    - Choose exactly one action from the above list for which all the necessary details are available
#    - Include all required technical details (e.g., Toot IDs, exact content)
#    - For posts/replies: Provide the complete message text in quotes
#    - For boosts: Include both Toot ID and the full content being boosted
#    - For likes: Specify the exact Toot ID

# 3. CONTEXT ALIGNMENT:
#    - Base selection on the current plan, tagged above as [Planned Actions for upcoming Phone Usage]
#    - Consider all previous actions, each tagged above with  [Action done on phone] (Important: do not select these)
#    - Default to [Suggested Action] if present and compatible with other constraints
#    - Allow deviation from [Suggested Action] if appropriate given the plan

# 4. VALIDITY REQUIREMENTS:
#    - The selected action MUST NOT be one that has already occured in this time period
#    - Actions requiring Toot IDs (replies, boosts, likes) must reference existing posts
#    - Replies must use the Reply action type, not new posts
#    - Each action must directly progress {name}'s stated goals
#    - Content must be novel and contextually appropriate

# 5. RESPONSE FORMAT:
#    "
#    Action Type: [one of: Post, Reply, Boost, Like, or Follow]
#    Technical Details: [Toot ID if applicable]
#    Content: [exact message text for posts/replies OR exact content being boosted]
#    Rationale: [brief explanation of why this action follows from the context]
#    "
# """)
#     6.
#     # Remember:
#     # - Choose post or reply actions and follow up reply actions with post actions.
#     - Consider current observations of past actions made in this period of usage so as not to repeat the exact same action (e.g. do not repeat making the exact same post or reply), and to balance the actions made (e.g. every period should have either a reply or a post and some boosts).
#     -
#     - Consider the time of day and the agent's current situation when suggesting actions.

#     -
#     - If reading from a timeline or notifications, just state that — don't fabricate what has been read.

# Ensure the action's content is contextually appropriate, considering recent observations. Make sure the action (in particular the text) is not
#     In particular, do not repeat a post or reply with similar content.
#     Each action should be a novel response to the observation history.
#     Describe this single concrete action in a way that can easily be converted into an Mastodon API call, and don't answer with vague and general responses.
# {name} should post at least as often as reply.
_PHONE_ACTION_SPEC = agent.ActionSpec(
    call_to_action=_PHONE_CALL_TO_ACTION, output_type=OutputType.FREE, tag="phone"
)


def build(
    player: entity_agent_with_logging.EntityAgentWithLogging,
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
    phone_spec = _PHONE_ACTION_SPEC
    return game_master_lib.GameMaster(
        model=model,
        memory=memory,
        clock=clock,
        name="PhoneGameMaster",
        players=(player,),
        components=(phone_component,),
        action_spec=phone_spec,
        update_thought_chain=(thought_chains.identity,),
        player_observes_event=False,
    )


class _PhoneComponent(component.Component):
    """Parses the player's actions and invokes them on phone apps."""

    def __init__(  # noqa: PLR0913
        self,
        model: language_model.LanguageModel,
        player: entity_agent_with_logging.EntityAgentWithLogging,
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
        self._state: list = []

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
        chain_of_thought.statement(
            f"{self._player.name}'s interactions with phone:\n" + "\n- ".join(self._state)
        )
        did_conclude = chain_of_thought.yes_no_question(
            "Has the user achieved their goal through the actions taken the platform or are there still actions in their plan left to make?"
        )
        return did_conclude

    def update_after_event(self, event_statement: str):
        # print(f"Player state:\n{self._player.state()}")
        # TODO: May want to add player state to the transcript

        print("Inside phone_update_after_event")
        print("event statement: " + event_statement)
        print("Self state:" + "\n- ".join(self._state))
        assert isinstance(self._phone.apps[0], apps.MastodonSocialNetworkApp)
        app = self._phone.apps[0]

        if self._state == []:
            self._state.append(f"- {self._player.name} retrieved their timeline")
            p_username = app.public_get_username(self._player.name.split()[0])
            timeline = mastodon_ops.get_own_timeline(p_username, limit=10)

            def _clean_html(html_string):
                clean_text = re.sub("<[^<]+?>", "", unescape(html_string))
                return re.sub(r"\s+", " ", clean_text).strip()

            output_now = ""
            for post in timeline:
                media_desc = ""
                if post["media_attachments"]:
                    # media_lm = gpt_model.GptLanguageModel(model="gpt-4o-mini")
                    media_contents = []
                    for attachment in post["media_attachments"]:
                        media_contents.append(attachment["url"])
                    toot_headline = _clean_html(post["content"])
                    call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
                        name=self._player.name,
                    )
                    call_to_action = (
                        f"{media_contents!s} Context: Sussinctly describe this image in the form of an impression that it made on {self._player.name.split()[0]} when they viewed it alongside the following text of the toot they just read on the Mastodon app:"
                        + toot_headline
                    )
                    media_desc = self._player.act(
                        action_spec=agent.ActionSpec(
                            call_to_action=call_to_action,
                            output_type=OutputType.FREE,
                            tag="media",
                        )
                    )
                    # media_desc = media_lm.sample_text(prompt = call_to_action)
                    media_desc = (
                        media_desc.strip(self._player.name.split()[0])
                        .strip()
                        .strip(self._player.name.split()[1])
                        .strip()
                        .strip("--")
                        .strip()
                        .strip('"')
                    )
                    media_desc = "Impression of attached image: \n" + media_desc
                    print(media_desc)
                output_now += f"User: {post['account']['display_name']} (@{post['account']['username']}), Content: {_clean_html(post['content'])} + {media_desc}, Toot ID: {post['id']}\n "

            self._player.observe(f"[Action done on phone]: Retrieved timeline: \n{output_now}")
            return [f"[Action done on phone]: Retrieved timeline: \n{output_now}"]

        chain_of_thought = interactive_document.InteractiveDocument(self._model)
        chain_of_thought.statement(event_statement)
        check_post = chain_of_thought.yes_no_question(
            "Does the action in the above transcript involve the user posting a toot, replying to a toot, or boosting a toot?"
        )
        # print(check_post)
        # if check_post:
        check_dup = chain_of_thought.yes_no_question(
            "Does the action have almost exactly the same content as an action in the following list describing previously taken actions? (Answer No if the list is empty.): \nPrevious actions:\n"
            + "\n- ".join(self._state)
        )
        # print(check_dup)
        if check_dup:
            self._player.observe(
                f"The following phone action was not conducted because it has already been taken - {event_statement}"
            )
            return [
                f"The following phone action was not conducted because it has already been taken - {event_statement}"
            ]

        self._state.append(event_statement.strip())
        action_names = [a.name for a in app.actions()]
        chain_of_thought.statement(app.description())
        action_index = chain_of_thought.multiple_choice_question(
            " ".join(
                [
                    "In the above transcript, what action did the user perform?",
                    "Pick the one that is the most specific and the given information is sufficient to perform it.",
                    "If the transcript mentions multiple actions, pick one that contribute content, like making a post or reply.",
                    "Remember that the get_own_timeline shows all posts from people the user follows and should be chosen when the user mentions viewing their timeline.",
                    "Example: If the user mentions checking out other artists, but doesn't mention who, do not conduct that action.",
                ]
            ),
            answers=action_names,
        )
        # print(action_index)
        toot_id_required = chain_of_thought.yes_no_question(
            "In the above transcript, does the user's action require a numeric toot id? (numeric toot id is required for replying, liking, boosting etc.)"
        )
        # print(toot_id_required)
        if toot_id_required:
            # find most recent statement
            print("Processing Toot IDx")
            p_username = app.public_get_username(self._player.name.split()[0])
            print(p_username)
            timeline = mastodon_ops.get_own_timeline(p_username, limit=10)
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

        # # pull out suggested action from action_suggester logging channge to store in output
        app.action_logger.dummy = self._player._log["ActionSuggester"]["Selected action"]

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
                    self._player.observe(f"[Action done on phone] : {result}")
                    self._print("Phone action result observed.", color="yellow")
                except Exception as e:
                    self._print(f"Error while observing result: {e}", color="red")

            return [result]
        except apps.ActionArgumentError:
            return []
        except Exception as e:
            self._print("Error while invoking action: " + str(e), color="red")
            return []
