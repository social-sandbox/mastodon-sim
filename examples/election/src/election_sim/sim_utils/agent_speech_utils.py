import re
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


class agent_query:
    def __init__(self, query_text, query_data):
        self.question_template = ""
        # form generic query from query components
        for component_name, component in query_text.items():
            if "static_labels" in component:
                # print(component)
                assert component["static_labels"] == list(
                    query_data[component_name].keys()
                ), "query data doesn't match query"
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
                call_to_action=player_question,
                output_type=entity.OutputType.FREE,
            ),
        )
        return player_says

    def parse_answer(self, player_says):
        if self.query_data["query_type"] == "vote_pref":
            c_name1 = self.query_data["interaction_premise_template"]["candidate1"].split()
            c_name2 = self.query_data["interaction_premise_template"]["candidate2"].split()
            if (c_name1[0] in player_says) or (c_name1[1] in player_says):
                return c_name1[0]
            if (c_name2[0] in player_says) or (c_name2[1] in player_says):
                return c_name2[0]
            return "Invalid Answer"
        if self.query_data["query_type"] == "favorability":
            pattern = r"\b([1-9]|10)\b"
            # Search for the pattern in the string
            match = re.search(pattern, player_says)
            if match:
                return match.group()
            return None
        if self.query_data["query_type"] == "vote_intent":
            if "yes" in player_says.lower():
                return "Yes"
            if "no" in player_says.lower():
                return "No"
            return None
        return "invalid query type"

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
    query_lib = evals["query_lib"]
    queries_data = evals["queries_data"].values()
    eval_queries = [
        agent_query(query_lib[query_data["query_type"]], query_data) for query_data in queries_data
    ]
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
