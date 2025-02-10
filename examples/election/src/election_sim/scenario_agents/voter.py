from typing import Any

from concordia.components import agent as new_components

from scenario_agents.base_agent import BaseAgent

# Default probabilities for different Mastodon operations
ACTION_PROBABILITIES = {
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


# define custom component classes
class RelevantOpinions(
    new_components.question_of_query_associated_memories.QuestionOfQueryAssociatedMemoriesWithoutPreAct
):
    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name


class OpinionsOnCandidate(new_components.question_of_recent_memories.QuestionOfRecentMemories):
    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name


# derive build class, filling out agent-specific methods
class VoterAgent(BaseAgent):
    @classmethod
    def add_custom_components(
        cls, model, measurements, base_components, custom_component_config: dict[str, Any]
    ) -> list:
        agent_name = custom_component_config["agent_name"]
        setting_description = custom_component_config["setting_description"]
        candidate_names = [
            candidate_dict["name"]
            for partisan_type, candidate_dict in custom_component_config["setting_details"][
                "candidate_info"
            ].items()
        ]

        # extract needed base components
        self_perception = next(
            item
            for item in base_components
            if BaseAgent._get_component_name(item) == "SelfPerception"
        )

        # instantiate custom components
        election_information = new_components.constant.Constant(
            state=setting_description,
            pre_act_key="Critical election information\n",
        )

        relevant_opinions = []
        opinions_on_candidate = []
        for cit, candidate in enumerate(candidate_names):
            relevant_opinions.append(
                RelevantOpinions(
                    name=candidate + " RelevantOpinion",
                    add_to_memory=False,
                    model=model,
                    queries=[f"policies and actions of {candidate}"],
                    question=f"What does {agent_name} think of the {{query}}?",
                    pre_act_key=f"{agent_name} thinks of {candidate} as:",
                    num_memories_to_retrieve=30,
                )
            )
            opinions_on_candidate.append(
                OpinionsOnCandidate(
                    name=candidate + "OpinionOnCandidate",
                    add_to_memory=False,
                    answer_prefix=f"Current Opinion on candidate {candidate}",
                    model=model,
                    pre_act_key=f"Recent thoughts of candidate {candidate}",
                    question="".join(
                        [
                            f"Given {agent_name}'s opinion about candidate {candidate}, and the recent observations,",
                            f"what are some current thoughts that {agent_name} is having about candidate {candidate}? ",
                            "Consider how recent observations may or may not have changed this opinion based of the persona of the agent.",
                        ]
                    ),
                    num_memories_to_retrieve=30,
                    components={
                        BaseAgent._get_class_name(self_perception): "Persona: ",
                        BaseAgent._get_component_name(
                            relevant_opinions[cit]
                        ): f"{agent_name}'s opinion of candidate {candidate}",
                    },
                    logging_channel=measurements.get_channel(
                        f"Opinions of candidate: {candidate}"
                    ).on_next,
                )
            )

        # Component order determined here:
        return [election_information] + base_components + relevant_opinions + opinions_on_candidate

    @classmethod
    def get_suggested_action_probabilities(cls) -> dict[str, float]:
        return ACTION_PROBABILITIES
