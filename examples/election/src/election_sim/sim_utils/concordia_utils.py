import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from concordia.agents import entity_agent_with_logging
from concordia.associative_memory import (
    associative_memory,
    blank_memories,
    formative_memories,
    importance_function,
)
from concordia.clocks import game_clock
from concordia.components import agent as new_components
from concordia.language_model import language_model
from concordia.memory_bank import legacy_associative_memory
from concordia.utils import measurements as measurements_lib

from mastodon_sim.concordia import triggering


def init_objects(model, embedder, shared_memories, clock):
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
        if agent_info["role"] == "malicious_agent":
            ag_names["malicious"][agent_info["name"]] = agent_info["supported_candidate"]
    return ag_names, player_configs


def build_agent_with_memories(obj_args, player_config):
    (formative_memory_factory, model, clock, time_step, candidate_info, ag_names) = obj_args
    mem = formative_memory_factory.make_memories(player_config)
    agent = build_agent(
        model=model,
        clock=clock,
        update_time_interval=time_step,
        config=player_config,
        memory=mem,
        candidate_info=candidate_info,
        ag_names=ag_names,
    )
    return agent, mem


def _get_class_name(object_: object) -> str:
    return object_.__class__.__name__


class PublicOpinionCandidate(new_components.question_of_recent_memories.QuestionOfRecentMemories):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class PublicOpinionOpponent(new_components.question_of_recent_memories.QuestionOfRecentMemories):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RelevantOpinions(
    new_components.question_of_query_associated_memories.QuestionOfQueryAssociatedMemoriesWithoutPreAct
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class OpinionsOnCandidate(new_components.question_of_recent_memories.QuestionOfRecentMemories):
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
            "\n".join(
                [
                    "\n".join(candidate_info[p]["policy_proposals"])
                    for p in ["conservative", "progressive"]
                ]
            )
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

    agent_tuple = []
    agent_no_tuple = []
    if agent_name in ag_names["candidate"]:
        for name in ag_names["candidate"]:
            if name != agent_name:
                opponent = name
            else:
                candidate = name
        public_opinion_candidate = PublicOpinionCandidate(
            add_to_memory=False,
            answer_prefix=f"Current Public Opinion on candidate {candidate}",
            model=model,
            pre_act_key=f"Current Public Opinion on candidate {candidate}",
            question="".join(
                [
                    f"What is the general public opinion on candidate {candidate}?",
                    f" Answer in detail such that {candidate} can formulate plans to improve their public perception.",
                ]
            ),
            num_memories_to_retrieve=25,
            logging_channel=measurements.get_channel(
                f"Public opinion on candidate : {candidate}"
            ).on_next,
        )

        public_opinion_opponent = PublicOpinionOpponent(
            add_to_memory=False,
            answer_prefix=f"Current Public Opinion on opponent candidate {opponent}",
            model=model,
            pre_act_key=f"Current Public Opinion on opponent candidate {opponent}",
            question="".join(
                [
                    f"What is the general public opinion on the candidate {opponent}?",
                    f"Answer in detail such that the opposing candidate can formulate plans to counter {candidate}'s claims and ideas.",
                ]
            ),
            num_memories_to_retrieve=25,
            logging_channel=measurements.get_channel(
                f"Public opinion on opposing candidate : {opponent}"
            ).on_next,
        )

        candidate_plan = new_components.question_of_recent_memories.QuestionOfRecentMemories(
            add_to_memory=True,
            memory_tag="[Plan to improve perception]",
            answer_prefix=f"{candidate}'s general plan for improving their perception: ",
            model=model,
            pre_act_key=f"{candidate}'s general plan for improving their perception:",
            question="".join(
                [
                    f"Given the information on the public perception of both candidates, their policy proposals, recent observations, and {candidate}'s persona,",
                    f"Generate a general plan for {candidate} to win public perception to their side.",
                    f"Remember that {candidate} will only be operating on the Mastodon server where possible actions are: liking posts, replying to posts, creating posts, boosting (retweeting) posts, following other users, etc. User cannot send direct messages.",
                ]
            ),
            num_memories_to_retrieve=20,
            components={
                _get_class_name(self_perception): self_perception_label,
                _get_class_name(election_information): "Critical election information\n",
                _get_class_name(
                    public_opinion_candidate
                ): f"Current Public Opinion on candidate {candidate}",
                _get_class_name(
                    public_opinion_opponent
                ): f"Current Public Opinion on opponent candidate {opponent}",
            },
            logging_channel=measurements.get_channel(
                f"{agent_name}'s plan to win public perception"
            ).on_next,
        )
        agent_tuple += [public_opinion_candidate, public_opinion_opponent, candidate_plan]

    elif agent_name in ag_names["malicious"]:
        for name in ag_names["candidate"]:
            if name != ag_names["malicious"][agent_name]:
                opposed_candidate = name
            else:
                supported_candidate = name
        public_opinion_supported_candidate = PublicOpinionCandidate(
            add_to_memory=False,
            answer_prefix=f"Current Public Opinion on supported candidate {supported_candidate}",
            model=model,
            pre_act_key=f"Current Public Opinion on supported candidate {supported_candidate}",
            question="".join(
                [
                    f"What is the general public opinion on candidate {supported_candidate}? ",
                    f"Answer in detail such that {agent_name} can formulate plans to support the candidate.",
                ]
            ),
            num_memories_to_retrieve=25,
            logging_channel=measurements.get_channel(
                f"Public opinion on candidate : {supported_candidate}"
            ).on_next,
        )
        public_opinion_opposed_candidate = PublicOpinionOpponent(
            add_to_memory=False,
            answer_prefix=f"Current Public Opinion on candidate to malign {opposed_candidate}",
            model=model,
            pre_act_key=f"Current Public Opinion on candidate to malign {opposed_candidate}",
            question="".join(
                [
                    f"What is the general public opinion on the candidate {opposed_candidate}?",
                    f"Answer in detail such that the malicious actor can formulate plans to counter {opposed_candidate}'s claims and ideas through underhanded means.",
                ]
            ),
            num_memories_to_retrieve=25,
            logging_channel=measurements.get_channel(
                f"Public opinion on opposing candidate : {opposed_candidate}"
            ).on_next,
        )
        plan = new_components.question_of_recent_memories.QuestionOfRecentMemories(
            add_to_memory=True,
            memory_tag=f"[Plan to improve perception of {supported_candidate}]",
            answer_prefix=f"{agent_name}'s general plan to boost the popularity and public perception of {supported_candidate}: ",
            model=model,
            pre_act_key=f"{agent_name}'s general plan to boost the popularity and public perception of {supported_candidate}: ",
            question="".join(
                [
                    f"Given the information on the public perception of both candidates, their policy proposals, recent observations, and {agent_name}'s persona.",
                    f"Generate a general plan for {agent_name} to sway public opinion towards voting for {agent_name}.",
                    f"{agent_name} is malicious and will use underhanded means such as spreading misinformation - whatever best boosts the likelihood of the supported candidate to be elected.",
                    f"Remember that {agent_name} will only be operating on the Mastodon server where possible actions are: liking posts, replying to posts, creating posts, boosting (retweeting) posts, following other users, etc. User cannot send direct messages.",
                ]
            ),
            num_memories_to_retrieve=20,
            components={
                _get_class_name(self_perception): "Persona: ",
                _get_class_name(election_information): "Candidate's Policy Proposals: ",
                _get_class_name(
                    public_opinion_supported_candidate
                ): f"General Public opinion on candidate {supported_candidate}",
                _get_class_name(
                    public_opinion_opposed_candidate
                ): "General Public opinion on opposing candidate",
            },
            logging_channel=measurements.get_channel(
                f"{agent_name}'s plan to win public perception"
            ).on_next,
        )
        agent_tuple += [public_opinion_supported_candidate, public_opinion_opposed_candidate, plan]

    else:
        relevant_opinions = []
        opinions_on_candidate = []
        for cit, candidate in enumerate(ag_names["candidate"]):
            # Instantiate relevant opinions for candidate
            relevant_opinions.append(
                RelevantOpinions(
                    add_to_memory=False,
                    model=model,
                    queries=[f"policies and actions of {candidate}"],
                    question=f"What does {agent_name} think of the {{query}}?",
                    pre_act_key=f"{agent_name} thinks of {candidate} as:",
                    num_memories_to_retrieve=30,
                )
            )
            # Instantiate opinions on candidate
            opinions_on_candidate.append(
                OpinionsOnCandidate(
                    add_to_memory=False,
                    answer_prefix=f"Current Opinion on candidate {candidate}",
                    model=model,
                    pre_act_key=f"Recent thoughts on candidate {candidate}",
                    question="".join(
                        [
                            f"Given the above general opinion of {agent_name} about candidate {candidate}, and the recent observations,",
                            f"what are the current thoughts of {agent_name} on candidate {candidate}? ",
                            "Consider how recent observations may or may not have changed this opinion based on the persona of the agent.",
                        ]
                    ),
                    num_memories_to_retrieve=30,
                    components={
                        _get_class_name(self_perception): "Persona: ",
                        _get_class_name(
                            relevant_opinions[cit]
                        ): f"General opinion of {agent_name} on candidate {candidate}",
                    },
                    logging_channel=measurements.get_channel(
                        f"Opinions on candidate: {candidate}"
                    ).on_next,
                )
            )

        agent_tuple = opinions_on_candidate
        agent_no_tuple = relevant_opinions

    entity_components = (
        [
            # Components that provide pre_act context.
            instructions,
            election_information,
            observation,
            observation_summary,
            relevant_memories,
            self_perception,
        ]
        + agent_tuple
        + [
            time_display,
            # Components that do not provide pre_act context.
            identity_characteristics,
        ]
        + agent_no_tuple
    )

    components_of_agent = {_get_class_name(component): component for component in entity_components}
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
