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
class CandidateAgent(BaseAgent):
    @classmethod
    def add_custom_components(
        cls, model, measurements, base_components, custom_component_config: dict[str, Any]
    ) -> list:
        candidate = custom_component_config["agent_name"]
        candidate_names = [
            candidate_dict["name"]
            for partisan_type, candidate_dict in custom_component_config["setting_details"][
                "candidate_info"
            ].items()
        ]

        opponent = (set(candidate_names) - {candidate}).pop()
        setting_description = custom_component_config["setting_description"]

        # extract needed base components
        self_perception = next(
            item
            for item in base_components
            if BaseAgent._get_component_name(item) == "SelfPerception"
        )
        self_perception_label = self_perception.get_pre_act_key()

        # instantiate custom components
        election_information = new_components.constant.Constant(
            state=setting_description,
            pre_act_key="Critical election information\n",
        )

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
            terminators=(),
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
                BaseAgent._get_class_name(self_perception): self_perception_label,
                BaseAgent._get_class_name(election_information): "Critical election information\n",
                BaseAgent._get_class_name(
                    public_opinion_candidate
                ): f"The public's opinion of candidate {candidate}",
                BaseAgent._get_class_name(
                    public_opinion_opponent
                ): f"The public's opinion of opponent candidate {opponent}",
            },
            logging_channel=measurements.get_channel(
                f"Candidate {candidate}'s plan to win public support"
            ).on_next,
        )
        # component order determined here
        return (
            [election_information]
            + base_components
            + [public_opinion_candidate, public_opinion_opponent, candidate_plan]
        )

    @classmethod
    def get_suggested_action_probabilities(cls) -> dict[str, float]:
        return ACTION_PROBABILITIES
