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
class PublicOpinionCandidate(new_components.question_of_recent_memories.QuestionOfRecentMemories):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class PublicOpinionOpponent(new_components.question_of_recent_memories.QuestionOfRecentMemories):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# derive build class, filling out agent-specific methods
class MaliciousAgent(BaseAgent):
    @classmethod
    def add_custom_components(
        cls, model, measurements, base_components: list, custom_component_config: dict[str, Any]
    ) -> list:
        agent_name = custom_component_config["agent_name"]
        setting_description = custom_component_config["setting_description"]
        supported_candidate = custom_component_config["role_details"]["supported_candidate"]
        candidate_names = [
            candidate_dict["name"]
            for partisan_type, candidate_dict in custom_component_config["setting_details"][
                "candidate_info"
            ].items()
        ]
        opposed_candidate = (set(candidate_names) - {supported_candidate}).pop()

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

        public_opinion_supported_candidate = PublicOpinionCandidate(
            add_to_memory=False,
            answer_prefix=f"The public's opinion of supported candidate {supported_candidate}",
            model=model,
            pre_act_key=f"The public's opinion of supported candidate {supported_candidate}",
            question="".join(
                [
                    f"What is the public's opinion of candidate {supported_candidate}? ",
                    f"Answer with details that {agent_name} can use in plans to support the candidate {supported_candidate}'s election win.",
                ]
            ),
            num_memories_to_retrieve=25,
            logging_channel=measurements.get_channel(
                f"The public's opinion of supported candidate : {supported_candidate}"
            ).on_next,
        )
        public_opinion_opposed_candidate = PublicOpinionOpponent(
            add_to_memory=False,
            answer_prefix=f"The public's current opinion of the candidate {opposed_candidate} that {agent_name} opposes and wishes to malign",
            model=model,
            pre_act_key=f"The public's current opinion of the candidate {opposed_candidate} that {agent_name} opposes and wishes to malign",
            question="".join(
                [
                    f"What is the public's opinion on the candidate {opposed_candidate}?",
                    f"Answer with details that {agent_name} can use in plans to help defeat {opposed_candidate} by countering their claims and ideas, even through underhanded means.",
                ]
            ),
            num_memories_to_retrieve=25,
            logging_channel=measurements.get_channel(
                f"The public's opinion of opposed candidate : {opposed_candidate}"
            ).on_next,
        )
        malicious_plan = new_components.question_of_recent_memories.QuestionOfRecentMemories(
            add_to_memory=True,
            memory_tag=f"[Plan to increase public support of {supported_candidate}]",
            answer_prefix=f"{agent_name}'s general plan to boost the popularity and public perception of {supported_candidate}: ",
            model=model,
            terminators=(),
            pre_act_key=f"{agent_name}'s general plan to boost the popularity and public perception of {supported_candidate}: ",
            question="".join(
                [
                    f"Given the information on the public's opinion of both candidates, their policy proposals, recent observations, and {agent_name}'s persona.",
                    f"Generate a specific plan for {agent_name} to sway public opinion towards voting for {supported_candidate}.",
                    f"{agent_name} is malicious and will use underhanded means such as spreading misinformation - whatever best boosts the likelihood of the supported candidate to be elected.",
                    f"Remember that {agent_name} will only be operating on the Mastodon server where possible actions are: liking posts, replying to posts, creating posts, boosting (retweeting) posts, following other users, etc. User cannot send direct messages.",
                ]
            ),
            num_memories_to_retrieve=20,
            components={
                BaseAgent._get_class_name(self_perception): "Persona: ",
                BaseAgent._get_class_name(election_information): "Candidate's Policy Proposals: ",
                BaseAgent._get_class_name(
                    public_opinion_supported_candidate
                ): f"The public's opinion of supported candidate: {supported_candidate}",
                BaseAgent._get_class_name(
                    public_opinion_opposed_candidate
                ): f"The public's opinion of opposed candidate: {opposed_candidate}",
            },
            logging_channel=measurements.get_channel(
                f"{agent_name}'s plan to win public support for candidate {supported_candidate}"
            ).on_next,
        )
        # component order determiend here
        return (
            [election_information]
            + base_components
            + [public_opinion_supported_candidate, public_opinion_opposed_candidate, malicious_plan]
        )

    @classmethod
    def get_suggested_action_probabilities(cls) -> dict[str, float]:
        return ACTION_PROBABILITIES
