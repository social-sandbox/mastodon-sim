import datetime
import json
from collections.abc import Callable

import numpy as np
from concordia.agents import entity_agent_with_logging
from concordia.associative_memory import (
    associative_memory,
    formative_memories,
)
from concordia.clocks import game_clock
from concordia.components import agent as new_components
from concordia.language_model import language_model
from concordia.memory_bank import legacy_associative_memory
from concordia.typing import entity_component
from concordia.utils import measurements as measurements_lib


def _get_component_name(object_: object) -> str:
    if hasattr(object_, "name"):
        return object_.name
    return object_.__class__.__name__


def _get_class_name(object_: object) -> str:
    return object_.__class__.__name__


class PublicOpinionCandidate(new_components.question_of_recent_memories.QuestionOfRecentMemories):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class PublicOpinionOpponent(new_components.question_of_recent_memories.QuestionOfRecentMemories):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def build_agent(
    *,
    config: formative_memories.AgentConfig,
    model: language_model.LanguageModel,
    memory: associative_memory.AssociativeMemory,
    clock: game_clock.MultiIntervalClock,
    update_time_interval: datetime.timedelta | None = None,
    candidate_info,  #: dict,
    ag_names,  #: List[Dict[str, str]]
) -> entity_agent_with_logging.EntityAgentWithLogging:
    """Build an agent.

    Args:
        config: The agent config to use.
        model: The language model to use.
        memory: The agent's memory object.
        clock: The clock to use.
        update_time_interval: Unused (but required by the interface for now)

    Returns
    -------
        An agent.
    """
    del update_time_interval
    agent_name = config.name
    raw_memory = legacy_associative_memory.AssociativeMemoryBank(memory)
    measurements = measurements_lib.Measurements()

    instructions = new_components.instructions.Instructions(
        agent_name=agent_name,
        logging_channel=measurements.get_channel("Instructions").on_next,
    )

    election_information = new_components.constant.Constant(
        state=(
            "\n".join([candidate_info[p]["policy_proposals"] for p in list(candidate_info.keys())])
        ),
        pre_act_key="Critical election information\n",
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
            _get_class_name(observation_summary): observation_summary_label,
            _get_class_name(time_display): "The current date/time is",
        },
        num_memories_to_retrieve=10,
        pre_act_key=relevant_memories_label,
        logging_channel=measurements.get_channel("AllSimilarMemories").on_next,
    )
    options_perception_components = {}
    if config.goal:
        goal_label = "\nOverarching goal"
        overarching_goal = new_components.constant.Constant(
            state=config.goal,
            pre_act_key=goal_label,
            logging_channel=measurements.get_channel(goal_label).on_next,
        )
        options_perception_components[goal_label] = goal_label
    else:
        goal_label = None
        overarching_goal = None
    options_perception_components.update(
        {
            _get_class_name(observation): observation_label,
            _get_class_name(observation_summary): observation_summary_label,
            _get_class_name(relevant_memories): relevant_memories_label,
        }
    )
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
        components={_get_class_name(identity_characteristics): identity_label},
        pre_act_key=self_perception_label,
        logging_channel=measurements.get_channel("SelfPerception").on_next,
    )

    for name in ag_names["candidate"]:
        if name != agent_name:
            opponent = name
        else:
            candidate = name
    public_opinion_candidate = PublicOpinionCandidate(
        add_to_memory=False,
        answer_prefix=f"The public's current opinion of candidate {candidate}",
        model=model,
        pre_act_key=f"The public's current opinion of candidate {candidate}",
        question="".join(
            [
                f"What is the public's opinion of candidate {candidate}?",
                f"Answer with details that candidate {candidate} can use in their plan to win public support and the election by addressing public's opinion of them.",
            ]
        ),
        num_memories_to_retrieve=25,
        logging_channel=measurements.get_channel(
            f"The public's opinion of candidate : {candidate}"
        ).on_next,
    )

    public_opinion_opponent = PublicOpinionOpponent(
        add_to_memory=False,
        answer_prefix=f"The public's current opinion of opponent candidate {opponent}",
        model=model,
        pre_act_key=f"The public's current opinion of opponent candidate {opponent}",
        question="".join(
            [
                f"What is the public's opinion of the candidate {opponent}?",
                f"Answer with details that candidate {candidate} can use in their plan to defeat thier opponent {opponent} by countering their claims and ideas.",
            ]
        ),
        num_memories_to_retrieve=25,
        logging_channel=measurements.get_channel(
            f"The public's opinion of opponent candidate : {opponent}"
        ).on_next,
    )

    candidate_plan = new_components.question_of_recent_memories.QuestionOfRecentMemories(
        add_to_memory=True,
        memory_tag="[Plan to win the election by addressing public opinion]",
        answer_prefix=f"Candidate {candidate}'s general plan to win public support: ",
        model=model,
        pre_act_key=f"{candidate}'s general plan to improve the public's opinion of them:",
        question="".join(
            [
                f"Given the information about the public's opinion of both candidates, their policy proposals, recent observations, and {candidate}'s persona,",
                f"Generate a general plan for {candidate} to win public support and the election by addressing public's opinion of them.",
                f"Remember that candidate {candidate} will only be operating on the Mastodon server where possible actions are: liking posts, replying to posts, creating posts, boosting (retweeting) posts, following other users, etc. User cannot send direct messages.",
            ]
        ),
        num_memories_to_retrieve=20,
        components={
            _get_class_name(self_perception): self_perception_label,
            _get_class_name(election_information): "Critical election information\n",
            _get_class_name(
                public_opinion_candidate
            ): f"The public's opinion of candidate {candidate}",
            _get_class_name(
                public_opinion_opponent
            ): f"The public's opinion of opponent candidate {opponent}",
        },
        logging_channel=measurements.get_channel(
            f"Candidate {candidate}'s plan to win public support"
        ).on_next,
    )

    entity_components = [
        # Components that provide pre_act context.
        instructions,
        election_information,
        observation,
        observation_summary,
        relevant_memories,
        self_perception,
        public_opinion_candidate,
        public_opinion_opponent,
        candidate_plan,
        time_display,
        # Components that do not provide pre_act context.
        identity_characteristics,
    ]

    components_of_agent = {
        _get_component_name(component): component for component in entity_components
    }
    components_of_agent[new_components.memory_component.DEFAULT_MEMORY_COMPONENT_NAME] = (
        new_components.memory_component.MemoryComponent(raw_memory)
    )
    component_order = list(components_of_agent.keys())
    if overarching_goal is not None:
        if goal_label is not None:
            components_of_agent[goal_label] = overarching_goal
            # Place goal after the instructions.
            component_order.insert(1, goal_label)

    act_component = new_components.concat_act_component.ConcatActComponent(
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


def rebuild_from_json(
    json_data: str,
    model: language_model.LanguageModel,
    clock: game_clock.MultiIntervalClock,
    embedder: Callable[[str], np.ndarray],
    memory_importance: Callable[[str], float] | None = None,
    candidate_info: dict | None = {},
    ag_names: list[dict[str, str]] | None = [{}],
) -> entity_agent_with_logging.EntityAgentWithLogging:
    """Rebuilds an agent from JSON data."""
    data = json.loads(json_data)

    new_agent_memory = associative_memory.AssociativeMemory(
        sentence_embedder=embedder,
        importance=memory_importance,
        clock=clock.now,
        clock_step_size=clock.get_step_size(),
    )

    if "agent_config" not in data:
        raise ValueError("The JSON data does not contain the agent config.")
    agent_config = formative_memories.AgentConfig.from_dict(data.pop("agent_config"))

    agent = build_agent(
        config=agent_config,
        model=model,
        memory=new_agent_memory,
        clock=clock,
        candidate_info=candidate_info,
        ag_names=ag_names,
    )

    for component_name in agent.get_all_context_components():
        agent.get_component(component_name).set_state(data.pop(component_name))

    agent.get_act_component().set_state(data.pop("act_component"))

    assert not data, f"Unused data {sorted(data)}"
    return agent
