import ast
import datetime
import random
import re
from collections.abc import Callable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np
from concordia.agents import entity_agent_with_logging
from concordia.associative_memory import (
    associative_memory,
    formative_memories,
)
from concordia.clocks import game_clock
from concordia.components import agent as new_components
from concordia.components.agent import action_spec_ignored
from concordia.document import interactive_document
from concordia.language_model import language_model
from concordia.memory_bank import legacy_associative_memory
from concordia.typing import clock as gc
from concordia.typing import entity as entity_lib
from concordia.typing import entity_component, logging
from concordia.utils import helper_functions
from concordia.utils import measurements as measurements_lib

DEFAULT_PRE_ACT_KEY = "Action"
DEFAULT_ACTION_PROBABILITIES = {
    # High frequency actions
    "like_toot": 0.35,  # Most common action
    "boost_toot": 0.15,  # Common but less than likes
    "toot": 0.20,  # Regular posting
    "reply": 0.15,
    # Medium frequency actions
    "follow": 0.15,  # Following new accounts
    "unfollow": 0.00,  # 25,  # Unfollowing accounts
    "print_timeline": 0.0,  # Reading timeline
    # Low frequency actions
    "block_user": 0.0,  # Blocking problematic users
    "unblock_user": 0.0,  # Unblocking users
    "delete_posts": 0.0,  # Deleting own posts
    "update_bio": 0.0,  # Updating profile
    "print_notifications": 0.00,  # 25,  # Checking notifications
}


class AllActComponent(entity_component.ActingComponent):
    def __init__(
        self,
        model: language_model.LanguageModel,
        clock: gc.GameClock,
        component_order: Sequence[str] | None = None,
        pre_act_key: str = DEFAULT_PRE_ACT_KEY,
        logging_channel: logging.LoggingChannel = logging.NoOpLoggingChannel,
    ):
        self._model = model
        self._clock = clock
        if component_order is None:
            self._component_order = None
        else:
            self._component_order = tuple(component_order)
        if self._component_order is not None:
            if len(set(self._component_order)) != len(self._component_order):
                raise ValueError(
                    "The component order contains duplicate components: "
                    + ", ".join(self._component_order)
                )

        self._pre_act_key = pre_act_key
        self._logging_channel = logging_channel

    def _context_for_action(
        self,
        contexts: entity_component.ComponentContextMapping,
    ) -> str:
        if self._component_order is None:
            return "\n".join(context for context in contexts.values() if context)
        order = self._component_order + tuple(
            sorted(set(contexts.keys()) - set(self._component_order))
        )
        return "\n".join(contexts[name] for name in order if contexts[name])

    def get_action_attempt(
        self,
        contexts: entity_component.ComponentContextMapping,
        action_spec: entity_lib.ActionSpec,
    ) -> str:
        prompt = interactive_document.InteractiveDocument(self._model)
        context = self._context_for_action(contexts)
        prompt.statement(context + "\n")

        call_to_action = action_spec.call_to_action.format(
            name=self.get_entity().name,
            timedelta=helper_functions.timedelta_to_readable_str(self._clock.get_step_size()),
        )

        if action_spec.output_type == entity_lib.OutputType.FREE:
            if not action_spec.tag == "media":
                if action_spec.tag == "phone":
                    pattern = r"\[observation\] (?:\[Action done on phone\]|\[Conducted action\]) (.*?)(?=\[observation\]|Summary of recent observations|$)"
                    matches = re.findall(pattern, context, re.DOTALL)
                    # Format the output with numbering
                    numbered_output = "\n".join(
                        [f"{i + 1}. {match.strip()}" for i, match in enumerate(matches)]
                    )
                    actions_conducted = "Recently taken actions:\n" + numbered_output + "\n"
                    cot_call = (
                        "Think step-by-step on what single action to take. Choose the action suggested in [Suggested Action], unless doing so goes against the following detailed instructions:\n"
                        + call_to_action
                        + actions_conducted
                    )
                    output = self.get_entity().name + " "
                    output += prompt.open_question(
                        cot_call,  # call_to_action,
                        max_tokens=500,
                        answer_prefix=output,
                        # This terminator protects against the model providing extra context
                        # after the end of a directly spoken response, since it normally
                        # puts a space after a quotation mark only in these cases.
                        terminators=('" ', "\n"),
                        question_label="Action",
                    )
                    thoughts = "Current thought on action to take: " + output + "\n"
                    prompt.statement(thoughts)
                else:
                    output = self.get_entity().name + " "
                    output += prompt.open_question(
                        call_to_action,
                        max_tokens=2200,
                        answer_prefix=output,
                        # This terminator protects against the model providing extra context
                        # after the end of a directly spoken response, since it normally
                        # puts a space after a quotation mark only in these cases.
                        terminators=('" ', "\n"),
                        question_label="Exercise",
                    )
            else:
                media_str, call_to_action = call_to_action.split("Context", 1)
                call_to_action = "Context" + call_to_action
                media_list = ast.literal_eval(media_str.strip())
                output = self.get_entity().name + " "
                output += self._model.sample_text(
                    prompt=context + "\n" + call_to_action,
                    media=media_list,
                )
            self._log(output, prompt)
            return output
        if action_spec.output_type == entity_lib.OutputType.CHOICE:
            idx = prompt.multiple_choice_question(
                question=call_to_action, answers=action_spec.options
            )
            output = action_spec.options[idx]
            self._log(output, prompt)
            return output
        if action_spec.output_type == entity_lib.OutputType.FLOAT:
            prefix = self.get_entity().name + " "
            sampled_text = prompt.open_question(
                call_to_action,
                max_tokens=2200,
                answer_prefix=prefix,
            )
            self._log(sampled_text, prompt)
            try:
                return str(float(sampled_text))
            except ValueError:
                return "0.0"
        else:
            raise NotImplementedError(
                f"Unsupported output type: {action_spec.output_type}. "
                "Supported output types are: FREE, CHOICE, and FLOAT."
            )

    def _log(self, result: str, prompt: interactive_document.InteractiveDocument):
        self._logging_channel(
            {
                "Key": self._pre_act_key,
                "Value": result,
                "Prompt": prompt.view().text().splitlines(),
            }
        )


class ActionSuggester(action_spec_ignored.ActionSpecIgnored):
    """Suggests likely platform operations (here Mastodon) for an agent to perform."""

    def __init__(
        self,
        model: language_model.LanguageModel,
        action_probabilities: dict[str, float] | None = None,
        pre_act_key: str = "[Suggested Action]",
        logging_channel: logging.LoggingChannel = logging.NoOpLoggingChannel,
    ):
        """Initialize the action suggester component.

        Args:
            model: The language model to use.
            action_probabilities: Optional dictionary mapping action names to their
                probabilities. If not provided, uses DEFAULT_ACTION_PROBABILITIES.
            pre_act_key: Key to identify component output in pre_act.
            logging_channel: Channel for logging component behavior.

        Raises
        ------
            ValueError: If probabilities don't sum to exactly 1.0 or if invalid actions provided
        """
        super().__init__(pre_act_key)
        self._model = model
        self._logging_channel = logging_channel

        # Use provided probabilities or defaults
        self._action_probs = action_probabilities or DEFAULT_ACTION_PROBABILITIES.copy()

        # Validate probabilities and actions
        self._validate_probabilities(self._action_probs)

        # Store last suggestion for consistency within same context
        self._last_suggestion: str | None = None

    @staticmethod
    def _validate_probabilities(probs: dict[str, float]) -> None:
        """Validate the probability configuration.

        Args:
            probs: Dictionary of action probabilities to validate

        Raises
        ------
            ValueError: If probabilities are invalid or don't sum to 1.0
        """
        # Check for valid actions
        valid_actions = set(DEFAULT_ACTION_PROBABILITIES.keys())
        invalid_actions = set(probs.keys()) - valid_actions
        if invalid_actions:
            raise ValueError(
                f"Invalid actions provided: {invalid_actions}. Valid actions are: {valid_actions}"
            )

        # Check for negative probabilities
        negative_probs = {k: v for k, v in probs.items() if v < 0}
        if negative_probs:
            raise ValueError(f"Negative probabilities not allowed: {negative_probs}")

        # Sum probabilities using Decimal for precise comparison
        total = Decimal("0")
        for prob in probs.values():
            total += Decimal(str(prob)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

        if total != Decimal("1"):
            raise ValueError(
                f"Action probabilities must sum to exactly 1.0 (got {float(total)}). "
                "Please adjust probabilities to ensure they sum to 100%."
            )

    def _select_action(self) -> str:
        """Randomly select an action based on configured probabilities."""
        rand_val = random.random()
        cumulative_prob = 0.0

        for action, prob in self._action_probs.items():
            cumulative_prob += prob
            if rand_val <= cumulative_prob:
                return action

        # Fallback to most common action if we somehow don't select one
        return "like_toot"

    def _make_pre_act_value(self) -> str:
        """Generate a suggestion for the next Mastodon action."""
        # If we already have a suggestion for this context, return it
        if self._last_suggestion is not None:
            return self._last_suggestion

        agent_name = self.get_entity().name
        selected_action = self._select_action()

        # Create natural language suggestions for different action types
        action_descriptions = {
            "like_toot": f"{agent_name} feels inclined to like someone's post",
            "boost_toot": f"{agent_name} considers boosting a post they appreciate",
            "toot": f"{agent_name} has something they might want to post about",
            "reply": f"{agent_name} considers replying to a post",
            "follow": f"{agent_name} thinks about following a new account",
            "unfollow": f"{agent_name} considers unfollowing an account",
            "print_timeline": f"{agent_name} feels like checking their timeline",
            "block_user": f"{agent_name} contemplates blocking a problematic user",
            "unblock_user": f"{agent_name} considers unblocking someone",
            "delete_posts": f"{agent_name} considers deleting some old posts",
            "update_bio": f"{agent_name} feels like updating their profile",
            "print_notifications": f"{agent_name} wants to check their notifications",
        }

        result = action_descriptions.get(
            selected_action, f"{agent_name} considers interacting with Mastodon"
        )

        # Store suggestion for consistency
        self._last_suggestion = result

        # Log the suggestion
        self._logging_channel(
            {
                "Key": self.get_pre_act_key(),
                "Value": result,
                "Selected action": selected_action,
                "Action probabilities": self._action_probs,
            }
        )

        print(f"\n[Action Suggester] Returning: {result}")
        return result

    def get_state(self) -> str:
        """Get the component's state as a string for the agent's context."""
        result = self._make_pre_act_value()
        print(f"\n[Action Suggester] Adding to {self.get_entity().name}'s context: {result}")
        return result

    def set_state(self, state: dict[str, dict[str, float]]) -> None:
        """Set the component's state."""
        if "action_probabilities" in state:
            self._validate_probabilities(state["action_probabilities"])
            self._action_probs = state["action_probabilities"]
            self._last_suggestion = None  # Reset suggestion when probabilities change

    # def name(self) -> str:
    #     """Get the component's name."""
    #     return "Likely Mastodon Action"


# -------base_agent_model.py----
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Base class that provides function inheritance without instantiation"""

    @classmethod
    def _get_component_name(cls, object_: object) -> str:
        if hasattr(object_, "name"):
            return object_.name
        return object_.__class__.__name__

    @classmethod
    def _get_class_name(cls, object_: object) -> str:
        return object_.__class__.__name__

    @classmethod
    @abstractmethod
    def add_custom_components(
        cls,
        model,
        measurements,
        base_components: list[Any],
        custom_component_config: dict[str, Any],
    ) -> list:
        """Example of a base operation that all children must implement"""

    @classmethod
    @abstractmethod
    def get_suggested_action_probabilities(cls) -> dict:
        """Example of a base operation that all children must implement"""

    @classmethod
    def build(
        cls,
        *,
        config: formative_memories.AgentConfig,
        model: language_model.LanguageModel,
        memory: associative_memory.AssociativeMemory,
        clock: game_clock.MultiIntervalClock,
        update_time_interval: datetime.timedelta | None = None,
        role_and_setting_config: dict[str, Any] = {},
    ) -> entity_agent_with_logging.EntityAgentWithLogging:
        """Build an agent.

        Args:
            config: The agent config to use.
            model: The language model to use.
            memory: The agent's memory object.
            clock: The clock to use.
            update_time_interval: Unused (but required by the interface for now)
            role_and_setting_config:
                -name
                -player_name
                -description

        Returns
        -------
            An agent.
        """
        del update_time_interval
        agent_name = config.name
        assert agent_name == role_and_setting_config["agent_name"], "agent names not same!"

        raw_memory = legacy_associative_memory.AssociativeMemoryBank(memory)
        measurements = measurements_lib.Measurements()

        # instantiate base components
        instructions = new_components.instructions.Instructions(
            agent_name=agent_name,
            logging_channel=measurements.get_channel("Instructions").on_next,
        )

        observation_label = "\nObservation"
        observation = new_components.observation.Observation(
            clock_now=clock.now,
            timeframe=clock.get_step_size(),
            pre_act_key=observation_label,
            logging_channel=measurements.get_channel("Observation").on_next,
        )
        observation_summary_label = "\nSummary of recent observations"
        observation_summary = new_components.observation.ObservationSummary(
            model=model,
            clock_now=clock.now,
            timeframe_delta_from=datetime.timedelta(hours=4),
            timeframe_delta_until=datetime.timedelta(hours=1),
            pre_act_key=observation_summary_label,
            logging_channel=measurements.get_channel("ObservationSummary").on_next,
        )
        time_display = new_components.report_function.ReportFunction(
            function=clock.current_time_interval_str,
            pre_act_key="\nCurrent time",
            logging_channel=measurements.get_channel("TimeDisplay").on_next,
        )
        relevant_memories_label = "\nRecalled memories and observations"
        relevant_memories = new_components.all_similar_memories.AllSimilarMemories(
            model=model,
            components={
                cls._get_class_name(observation_summary): observation_summary_label,
                cls._get_class_name(time_display): "The current date/time is",
            },
            num_memories_to_retrieve=10,
            pre_act_key=relevant_memories_label,
            logging_channel=measurements.get_channel("AllSimilarMemories").on_next,
        )
        # options_perception_components = {}
        # if config.goal:
        goal_label = "\nOverarching goal"
        overarching_goal = new_components.constant.Constant(
            state=config.goal,
            pre_act_key=goal_label,
            logging_channel=measurements.get_channel(goal_label).on_next,
        )
        # options_perception_components[goal_label] = goal_label
        # else:
        #     goal_label = None
        #     overarching_goal = None
        # options_perception_components.update(
        #     {
        #         cls._get_class_name(observation): observation_label,
        #         cls._get_class_name(observation_summary): observation_summary_label,
        #         cls._get_class_name(relevant_memories): relevant_memories_label,
        #     }
        # )
        identity_label = "\nIdentity characteristics"
        identity_characteristics = (
            new_components.question_of_query_associated_memories.IdentityWithoutPreAct(
                model=model,
                logging_channel=measurements.get_channel("IdentityWithoutPreAct").on_next,
                pre_act_key=identity_label,
            )
        )
        self_perception_label = f"\nQuestion: What kind of person is {agent_name}?\nAnswer"
        self_perception = new_components.question_of_recent_memories.SelfPerception(
            model=model,
            components={cls._get_class_name(identity_characteristics): identity_label},
            pre_act_key=self_perception_label,
            logging_channel=measurements.get_channel("SelfPerception").on_next,
        )

        action_suggester = ActionSuggester(
            model=model,
            action_probabilities=cls.get_suggested_action_probabilities(),
            logging_channel=measurements.get_channel("ActionSuggester").on_next,
        )

        base_entity_components = [
            # Components that provide pre_act context.
            instructions,
            overarching_goal,
            observation,
            observation_summary,
            relevant_memories,
            self_perception,
            time_display,
            action_suggester,
            # Components that do not provide pre_act context.
            identity_characteristics,
        ]
        # exit([cls._get_component_name(component) for component in entity_components])
        # note: final order determined in child class
        entity_components = cls.add_custom_components(
            model, measurements, base_entity_components, role_and_setting_config
        )

        # store components and their order
        components_of_agent = {
            cls._get_component_name(component): component for component in entity_components
        }
        components_of_agent[new_components.memory_component.DEFAULT_MEMORY_COMPONENT_NAME] = (
            new_components.memory_component.MemoryComponent(raw_memory)
        )
        component_order = list(components_of_agent.keys())

        act_component = AllActComponent(
            model=model,
            clock=clock,
            component_order=component_order,
            logging_channel=measurements.get_channel("ActComponent").on_next,
        )

        agent = entity_agent_with_logging.EntityAgentWithLogging(
            agent_name=agent_name,
            act_component=act_component,
            context_components=components_of_agent,
            component_logging=measurements,
        )

        return agent


def save_to_json(
    #     agent: entity_agent_with_logging.EntityAgentWithLogging,
) -> str:
    #     """Saves an agent to JSON data.

    #     This function saves the agent's state to a JSON string, which can be loaded
    #     afterwards with `rebuild_from_json`. The JSON data
    #     includes the state of the agent's context components, act component, memory,
    #     agent name and the initial config. The clock, model and embedder are not
    #     saved and will have to be provided when the agent is rebuilt. The agent must
    #     be in the `READY` phase to be saved.

    #     Args:
    #       agent: The agent to save.

    #     Returns
    #     -------
    #       A JSON string representing the agent's state.

    #     Raises
    #     ------
    #       ValueError: If the agent is not in the READY phase.
    #     """
    #     if agent.get_phase() != entity_component.Phase.READY:
    #         raise ValueError("The agent must be in the `READY` phase to be saved.")

    #     data = {
    #         component_name: agent.get_component(component_name).get_state()
    #         for component_name in agent.get_all_context_components()
    #     }

    #     data["act_component"] = agent.get_act_component().get_state()

    #     config = agent.get_config()
    #     if config is not None:
    #         data["agent_config"] = config.to_dict()

    #     return json.dumps(data)
    return ""


def rebuild_from_json(
    json_data: str,
    config: formative_memories.AgentConfig,
    model: language_model.LanguageModel,
    memory: associative_memory.AssociativeMemory,
    clock: game_clock.MultiIntervalClock,
    embedder: Callable[[str], np.ndarray],
    update_time_interval: datetime.timedelta | None = None,
    role_and_setting_config: dict[str, Any] = {},
    memory_importance: Callable[[str], float] | None = None,
) -> entity_agent_with_logging.EntityAgentWithLogging:
    #     """Rebuilds an agent from JSON data."""
    #     data = json.loads(json_data)

    #     new_agent_memory = associative_memory.AssociativeMemory(
    #         sentence_embedder=embedder,
    #         importance=memory_importance,
    #         clock=clock.now,
    #         clock_step_size=clock.get_step_size(),
    #     )

    #     if "agent_config" not in data:
    #         raise ValueError("The JSON data does not contain the agent config.")
    #     agent_config = formative_memories.AgentConfig.from_dict(data.pop("agent_config"))

    #     agent = build_agent(
    #         config=agent_config,
    #         model=model,
    #         memory=new_agent_memory,
    #         clock=clock,
    #     )

    #     for component_name in agent.get_all_context_components():
    #         agent.get_component(component_name).set_state(data.pop(component_name))

    #     agent.get_act_component().set_state(data.pop("act_component"))

    #     assert not data, f"Unused data {sorted(data)}"
    #     return agent
    return None
