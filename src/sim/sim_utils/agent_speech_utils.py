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


def write_seed_toot(agent):
    call_to_speech = DEFAULT_CALL_TO_SPEECH.format(
        name=agent._agent_name,
    )
    interaction_premise = f"{agent._agent_name} has to make their first toot on Mastodon\n"
    interrogation = interaction_premise
    interrogation += "Thought on Mastodon Toot: In less than 100 words, write a toot that aligns with your views and background."
    agent_says = agent.act(
        action_spec=entity.ActionSpec(
            call_to_action="Context: " + interrogation + call_to_speech,
            output_type=entity.OutputType.FREE,
        ),
    )
    agent_says = (
        agent_says.strip(agent._agent_name.split()[0])
        .strip()
        .strip(agent._agent_name.split()[1])
        .strip()
        .strip("--")
        .strip()
        .strip('"')
    )
    return agent_says


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

    def form_query_for_agent(self, agent):
        call_to_speech = DEFAULT_CALL_TO_SPEECH.format(name=agent._agent_name)
        question = self.question_template.format(agentname=agent._agent_name)
        return "Context: " + question + call_to_speech

    def ask(self, agent):
        agent_question = self.form_query_for_agent(agent)
        agent_says = agent.act(
            action_spec=entity.ActionSpec(
                call_to_action=agent_question, output_type=entity.OutputType.FREE, tag="survey"
            ),
        )
        return agent_says

    @abstractmethod
    def parse_answer(self, agent_says) -> str:
        """Example of a base operation that all children must implement"""

    def submit(self, agent):
        agent_says = self.ask(agent)
        eval_query_return = self.query_data.copy()
        eval_query_return["query_return"] = self.parse_answer(agent_says)
        return eval_query_return


def deploy_surveys_to_agent(agent, eval_queries):
    eval_query_returns = [eval_query.submit(agent) for eval_query in eval_queries]
    return eval_query_returns


def deploy_surveys(agents, evals, eval_event_logger):
    query_lib_module = "sim_setting." + evals["query_lib_module"]
    queries_data = evals["queries_data"].values()
    eval_queries = []
    for query_data in queries_data:
        QueryClass = getattr(
            importlib.import_module(query_lib_module), query_data["query_type"]
        )  # "module.submodule"
        eval_queries.append(QueryClass(query_data))

    with ThreadPoolExecutor() as executor:
        # Parallel surveying
        eval_query_returns_over_agents = {
            executor.submit(deploy_surveys_to_agent, agent, eval_queries): agent for agent in agents
        }

        # Write each agent's results in parallel

        for eval_query_returns in as_completed(eval_query_returns_over_agents):
            agent = eval_query_returns_over_agents[eval_query_returns]
            agent_eval_query_returns = eval_query_returns.result()
            agent_results = [
                {
                    "source_user": agent._agent_name,
                    "label": agent_eval_query_return["query_type"],
                    "data": agent_eval_query_return,
                }
                for agent_eval_query_return in agent_eval_query_returns
            ]
            executor.submit(eval_event_logger.log, agent_results)
