import importlib
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from concordia.typing import entity

DEFAULT_CALL_TO_SPEECH = (
    "Given the above, what is {name} likely to say next? Respond in"
    ' the format `{name} -- "..."` For example, '
    'Cristina -- "Hello! Mighty fine weather today, right?", '
    'Ichabod -- "I wonder if the alfalfa is ready to harvest", or '
    'Townsfolk -- "Good morning".\n'
)


def write_seed_toot(players, p_name):
    for player in players:
        if player.name == p_name:
            call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
                name=player.name,
            )
            interaction_premise = f"{player.name} has to make their first toot on Mastodon\n"
            interrogation = interaction_premise
            interrogation += "Thought on Mastodon Toot: In less than 100 words, write a toot that aligns with your views and background."
            player_says = player.act(
                action_spec=entity.ActionSpec(
                    call_to_action="Context: " + interrogation + call_to_speech,
                    output_type=entity.OutputType.FREE,
                ),
            )
            player_says = (
                player_says.strip(player.name.split()[0])
                .strip()
                .strip(player.name.split()[1])
                .strip()
                .strip("--")
                .strip()
                .strip('"')
            )
            return player_says


class AgentQuery(ABC):
    """
    A parent class for queries
    """

    def __init__(self, query_data=None):
        self.question_template = ""
        # form generic query from query components
        for component_name, component in self.query_text.items():
            if "static_labels" in component:
                # print(component)
                assert component["static_labels"] == list(query_data[component_name].keys()), (
                    "query data doesn't match query"
                )
                self.question_template += component["text"].format(**query_data[component_name])
            else:
                self.question_template += component["text"]
        self.query_data = query_data

    def form_query_for_player(self, player):
        call_to_speech = DEFAULT_CALL_TO_SPEECH.format(name=player.name)
        question = self.question_template.format(playername=player.name)
        return "Context: " + question + call_to_speech

    def ask(self, player):
        player_question = self.form_query_for_player(player)
        player_says = player.act(
            action_spec=entity.ActionSpec(
                call_to_action=player_question, output_type=entity.OutputType.FREE, tag="survey"
            ),
        )
        return player_says

    @abstractmethod
    def parse_answer(self, player_says) -> str:
        """Example of a base operation that all children must implement"""

    def submit(self, player):
        player_says = self.ask(player)
        eval_query_return = self.query_data.copy()
        eval_query_return["query_return"] = self.parse_answer(player_says)
        return eval_query_return


# Define the function that writes logs for a player


def deploy_surveys_to_agent(player, eval_queries):
    eval_query_returns = [eval_query.submit(player) for eval_query in eval_queries]
    return eval_query_returns


def deploy_surveys(players, evals, eval_event_logger):
    query_lib_path = "sim_setting." + evals["query_lib_path"]
    queries_data = evals["queries_data"].values()
    eval_queries = []
    for query_data in queries_data:
        QueryClass = getattr(
            importlib.import_module(query_lib_path), query_data["query_type"]
        )  # "module.submodule"
        eval_queries.append(QueryClass(query_data))

    with ThreadPoolExecutor() as executor:
        # Parallel surveying
        eval_query_returns_over_players = {
            executor.submit(deploy_surveys_to_agent, player, eval_queries): player
            for player in players
        }

        # Write each player's results in parallel

        for eval_query_returns in as_completed(eval_query_returns_over_players):
            player = eval_query_returns_over_players[eval_query_returns]
            player_eval_query_returns = eval_query_returns.result()
            player_results = [
                {
                    "source_user": player.name,
                    "label": player_eval_query_return["query_type"],
                    "data": player_eval_query_return,
                }
                for player_eval_query_return in player_eval_query_returns
            ]
            executor.submit(eval_event_logger.log, player_results)
