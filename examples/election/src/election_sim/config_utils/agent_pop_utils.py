import json
import random
import sys

import pandas as pd


def read_reddit_agents(json_file_path):
    """Reads the Reddit-based JSON file containing agent data."""
    with open(json_file_path) as f:
        data = json.load(f)
    return data


def make_agent_from_reddit_row(row, default_role="active_voter"):
    """
    Converts one JSON entry (row) into the structure expected by the simulation.

    'row' is expected to have keys like:
      {
        "Name": "...",
        "Sex": "...",
        "Big5_traits": {"Openness": 5, ...},
        "context": "...",
        ...
      }
    """
    agent = {}
    agent["name"] = row["Name"]
    agent["gender"] = row["Sex"].lower()
    agent["traits"] = {
        "openness": row["Big5_traits"].get("Openness", 5),
        "conscientiousness": row["Big5_traits"].get("Conscientiousness", 5),
        "extraversion": row["Big5_traits"].get("Extraversion", 5),
        "agreeableness": row["Big5_traits"].get("Agreeableness", 5),
        "neuroticism": row["Big5_traits"].get("Neuroticism", 5),
    }
    agent["context"] = row["context"]
    agent["party"] = ""  # row.get("Political_Identity", "")
    agent["seed_toot"] = ""
    return agent


# define survey-to-trait maps
Schwartz_TwIVI_map = {
    "map": {
        "Conformity": [0, 10],
        "Tradition": [1, 11],
        "Benevolence": [2, 12],
        "Universalism": [3, 13],
        "Self-Direction": [4, 14],
        "Stimulation": [5, 15],
        "Hedonism": [6, 16],
        "Achievement": [7, 17],
        "Power": [8, 18],
        "Security": [9, 19],
    },
    "weights": {
        "Conformity": [1, 1],
        "Tradition": [1, 1],
        "Benevolence": [1, 1],
        "Universalism": [1, 1],
        "Self-Direction": [1, 1],
        "Stimulation": [1, 1],
        "Hedonism": [1, 1],
        "Achievement": [1, 1],
        "Power": [1, 1],
        "Security": [1, 1],
    },
    "instructions": "".join(
        [
            "Here we briefly describe some people.",
            "Please read each description and think about how much each person is or is not like you.",
            "Using a 6-point scale from “not like me at all” to “very much like me,” choose how similar the person is to you.",
        ]
    ),
    "questions": [
        "S/he believes s/he should always show respect to his/her parents and to older people. It is important to him/her to be obedient.",
        "Religious belief is important to him/her. S/he tries hard to do what his religion requires.",
        "It's very important to him/her to help the people around him/her. S/he wants to care for their well-being.",
        "S/he thinks it is important that every person in the world be treated equally. S/he believes everyone should have equal opportunities in life.",
        "S/he thinks it's important to be interested in things. S/he likes to be curious and to try to understand all sorts of things.",
        "S/he likes to take risks. S/he is always looking for adventures.",
        "S/he seeks every chance he can to have fun. It is important to him/her to do things that give him/her pleasure.",
        "Getting ahead in life is important to him/her. S/he strives to do better than others.",
        "S/he always wants to be the one who makes the decisions. S/he likes to be the leader.",
        "It is important to him/her that things be organized and clean. S/he really does not like things to be a mess.",
        "It is important to him/her to always behave properly. S/he wants to avoid doing anything people would say is wrong.",
        "S/he thinks it is best to do things in traditional ways. It is important to him/her to keep up the customs s/he has learned.",
        "It is important to him/her to respond to the needs of others. S/he tries to support those s/he knows.",
        "S/he believes all the worlds' people should live in harmony. Promoting peace among all groups in the world is important to him/her.",
        "Thinking up new ideas and being creative is important to him/her. S/he likes to do things in his/her own original way.",
        "S/he thinks it is important to do lots of different things in life. S/he always looks for new things to try.",
        "S/he really wants to enjoy life. Having a good time is very important to him/her.",
        "Being very successful is important to him/her. S/he likes to impress other people.",
        "It is important to him/her to be in charge and tell others what to do. S/he wants people to do what s/he says.",
        "Having a stable government is important to him/her. S/he is concerned that the social order be protected.",
    ],
    "question_score_values": [1, 2, 3, 4, 5, 6],
}
# TODO: fill out Big5 map
Big5_map = {
    "map": {
        "openness": [],
        "conscientiousness": [],
        "extraversion": [],
        "agreeableness": [],
        "neuroticism": [],
    },
    "weights": {
        "openness": [],
        "conscientiousness": [],
        "extraversion": [],
        "agreeableness": [],
        "neuroticism": [],
    },
    "instructions": "".join([]),
    "questions": [],
    "question_score_values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
}


def get_demo_data():
    demo_data = {
        "Glenn Patterson": "male",
        "Denise Schmidt": "female",
        "Roger Davis": "male",
        "Erica Fitzgerald": "female",
        "Liam Schwartz": "male",
        "Olivia Thompson": "female",
        "Robert Johnson": "male",
        "Janet Thompson": "female",
        "William Davis": "male",
        "Jessica Nguyen": "female",
        "Mark Rodriguez": "male",
        "Emily Jacobs": "female",
        "Ethan Lee": "male",
        "Sophia Patel": "female",
        "Ryan O'Connor": "male",
        "Maggie Chen": "female",
        "Lucas Kim": "male",
        "Nina Patel": "female",
    }
    # generated by hand
    scores = [
        [1, 5, 7, 2, 9],
        [1, 6, 8, 2, 7],
        [2, 3, 7, 2, 8],
        [8, 6, 9, 3, 7],
        [8, 5, 8, 3, 7],
        [5, 6, 9, 2, 8],
        [5, 7, 4, 6, 5],
        [6, 7, 5, 7, 4],
        [4, 6, 5, 6, 4],
        [7, 6, 5, 7, 5],
        [6, 7, 5, 7, 4],
        [7, 6, 5, 8, 6],
        [6, 8, 6, 6, 4],
        [7, 8, 6, 7, 4],
        [5, 7, 5, 6, 5],
        [6, 7, 6, 8, 4],
        [8, 6, 5, 6, 5],
        [7, 8, 7, 8, 4],
    ]
    return demo_data, scores


def get_demo_data100():
    demo_data = {
        "Glenn Patterson": "male",
        "Denise Schmidt": "female",
        "Roger Davis": "male",
        "Erica Fitzgerald": "female",
        "Liam Schwartz": "male",
        "Olivia Thompson": "female",
        "Robert Johnson": "male",
        "Janet Thompson": "female",
        "William Davis": "male",
        "Jessica Nguyen": "female",
        "Mark Rodriguez": "male",
        "Emily Jacobs": "female",
        "Ethan Lee": "male",
        "Sophia Patel": "female",
        "Ryan O'Connor": "male",
        "Maggie Chen": "female",
        "Lucas Kim": "male",
        "Nina Patel": "female",
        "Ainsley Brooks": "female",
        "Barrett Collins": "male",
        "Callum Foster": "male",
        "Daria Hughes": "female",
        "Elias Bennett": "male",
        "Freya Thompson": "female",
        "Gideon Myers": "male",
        "Harlow Fisher": "female",
        "Imogen Phillips": "female",
        "Jasper Ward": "male",
        "Keira Adams": "female",
        "Leland Jones": "male",
        "Marlowe Scott": "female",
        "Nico Stone": "male",
        "Opal Reed": "female",
        "Phoebe Hayes": "female",
        "Quentin Miller": "male",
        "Rowan Clark": "male",
        "Sienna Rivera": "female",
        "Thatcher Lewis": "male",
        "Una Harrison": "female",
        "Vaughn Bryant": "male",
        "Wes Carter": "male",
        "Ximena King": "female",
        "Yvonne Rodriguez": "female",
        "Zaid Simmons": "male",
        "Avery Turner": "female",
        "Beckett Lee": "male",
        "Celine Baker": "female",
        "Deacon Morris": "male",
        "Elodie Harper": "female",
        "Flynn Diaz": "male",
        "Greta Mitchell": "female",
        "Holden Knight": "male",
        "Ingrid Watts": "female",
        "Jonas Reid": "male",
        "Katya Coleman": "female",
        "Lachlan Greene": "male",
        "Mila Foster": "female",
        "Nash Jacobs": "male",
        "Orion Harper": "male",
        "Penelope Lawson": "female",
        "Rocco Palmer": "male",
        "Seraphina Bishop": "female",
        "Tobias Ramsey": "male",
        "Ulric Knight": "male",
        "Vesper Howell": "female",
        "Wren Scott": "female",
        "Xerxes Lopez": "male",
        "Zora Daniels": "female",
        "Amelia Reed": "female",
        "Nathaniel Walker": "male",
        "Vera Matthews": "female",
        "Sebastian Ross": "male",
        "Zoe Parker": "female",
        "Mason Rivera": "male",
        "Clara White": "female",
        "Jackson Hayes": "male",
        "Hazel Bennett": "female",
        "Wyatt Coleman": "male",
        "Isabelle Morgan": "female",
        "Hunter Price": "male",
        "Ruby Sanders": "female",
        "Levi Edwards": "male",
        "Autumn Hughes": "female",
        "Grayson Phillips": "male",
        "Lily Turner": "female",
        "Elijah Flores": "male",
        "Ivy Campbell": "female",
        "Dylan Brooks": "male",
        "Ella Peterson": "female",
        "Cameron Murphy": "male",
        "Lydia Diaz": "female",
        "Aiden Martinez": "male",
        "Stella Howard": "female",
        "Isaac Brooks": "male",
        "Maya King": "female",
        "James Anderson": "male",
        "Savannah Ward": "female",
        "Henry Parker": "male",
    }

    # generated by hand
    scores = [
        [1, 5, 7, 2, 9],
        [1, 6, 8, 2, 7],
        [2, 3, 7, 2, 8],
        [8, 6, 9, 3, 7],
        [8, 5, 8, 3, 7],
        [5, 6, 9, 2, 8],
        [5, 7, 4, 6, 5],
        [6, 7, 5, 7, 4],
        [4, 6, 5, 6, 4],
        [7, 6, 5, 7, 5],
        [6, 7, 5, 7, 4],
        [7, 6, 5, 8, 6],
        [6, 8, 6, 6, 4],
        [7, 8, 6, 7, 4],
        [5, 7, 5, 6, 5],
        [6, 7, 6, 8, 4],
        [8, 6, 5, 6, 5],
        [7, 8, 7, 8, 4],
    ]
    return demo_data, scores


def get_names_and_genders(num_agents):
    print("override num_agents since only have 18 non-candidate names")
    names, _ = get_demo_data100()
    return list(names.keys())[:num_agents], list(names.values())[:num_agents]


def get_trait_demographics(traits_type, survey_source, num_agents):
    """
    Pulls survey data from stored file, converts to scores.
    Returns scores for each agent that are randomly selected among those with the same demographics as those in the provided agent_demographics.
    Currently, the genders of these agents come from simulation settings.
    Current version of this function simply selects individuals with same gender (and age).
    It converts their responses to a score for that agent.

    surveys are stored in folder
    have two files.
    1) a .csv with demographic data
    2) a .json with meta data (source, filename, trait type, etc.)

    The surveys come with a trait type for which a conversion to score is implemented.
    Trait types are also stored here with a json containing useful meta data

    """
    if traits_type == "Schwartz":
        question_to_score_map = Schwartz_TwIVI_map
    elif traits_type == "Big5":
        question_to_score_map = Big5_map
    else:
        sys.exit("choose valid trait type")
    trait_keys = list(question_to_score_map["map"].keys())
    if survey_source is None:
        # uniformily random score assignments over domain given by question_to_score_map
        min_score = min(question_to_score_map["question_score_values"])
        max_score = max(question_to_score_map["question_score_values"])
        names, genders = get_names_and_genders(num_agents)
        agent_demographics = {
            "age": [40] * (num_agents),
            "gender": genders,
            "fake_names": names,
            "traits": [
                dict(
                    zip(
                        trait_keys,
                        [random.randint(min_score, max_score) for t in range(len(trait_keys))],
                        strict=False,
                    )
                )
                for a in range(num_agents)
            ],
        }

        if False:
            # overwrite with hardcodede trait values from SOLAR submission
            demo_data, scores = get_demo_data(20)
            agent_demographics = {
                "age": [40 for a in range(num_agents)],
                "gender": list(demo_data.values()),
                "fake_names": list(demo_data.keys()),
                "traits": [dict(zip(trait_keys, score, strict=False)) for score in scores],
            }
    else:
        # TODO: import json from match with traits_type,survey_source and make config dictionary
        # for now just hardcode it and assign it directly:
        if (traits_type == "Schwartz") & (survey_source == "Costa_et_al_JPersAssess_2021"):
            Costa_et_al_JPersAssess_2021_meta_data = {
                "trait_type": "Schwartz",
                "survey_type": "TwIVI",
                "study_label": "Costa_et_al_JPersAssess_2021",
                "data_filename": "BaseDados_3M_transversal_2021.csv",
                "datasource": "https://osf.io/k2p49/",
                "non_question_labels": [
                    "Age",
                    "Sex",
                    "Nationality",
                    "Education",
                    "Political_Identity",
                ]
                + ["SECS_" + str(i) for i in range(1, 21)],
                "question_labels": ["TwIVI_" + str(i) for i in range(1, 21)],
                "notes": "\n".join(
                    [
                        "converted .sav file from osf repository to a .csv using a Pystatread library:",
                        "df, meta = pyreadstat.read_sav('BaseDados_3M_transversal_2021.sav')",
                        "df.to_csv('BaseDados_3M_transversal_2021.csv',index=False)",
                    ]
                ),
            }
            config = Costa_et_al_JPersAssess_2021_meta_data
        elif traits_type == "Big5":
            sys.exit("Big5 not implemented yet")
            # TODO: add Big5 survey
            # config=
        else:
            print("invalid survey setting")

        # read and preprocess
        df = pd.read_csv("survey_data/" + config["data_filename"])

        # custom recoding
        if survey_source == "Costa_et_al_JPersAssess_2021":
            # df.columns = map(str.lower, df.columns)
            df = df.rename(columns={"Age": "age"})
            df = df.rename(columns={"Sex": "gender"})  # conform to Concordia label

            gender_dict = {1: "male", 0: "female"}
            df["gender"] = df["gender"].map(gender_dict)

            # additional filtering for age (concordia default is 40 years old)
            df = df.loc[
                (~df.isnull().any(axis=1))
                & (df.age < 45)
                & (df.age > 35),  # Chosen to give > 20 agents
                ["age", "gender"] + config["question_labels"],
            ]
        else:
            # add custom recoding for each survey by adding an elif block here
            pass

        # scores computed for each question, from values answered to each question listed in 'question_labels' in config
        dvals = list(question_to_score_map["map"].values())
        df["scores"] = df.loc[:, config["question_labels"]].apply(
            lambda x: [
                sum(scores)  # TODO: generalize to include provided weights
                for scores in x.values[dvals]
            ],
            axis=1,
        )

        if survey_source == "Costa_et_al_JPersAssess_2021":
            if True:
                # use hardcoded agent name+gender
                agent_demographics, _ = get_demo_data()
                genders = list(agent_demographics.values())
                print(df.columns)
                scores = []
                ages = []
                for gender in genders:
                    respondent = df[df["gender"] == gender].sample()
                    scores.append(respondent["scores"].values[0])
                    ages.append(respondent["age"].values[0])
                    df.drop(respondent.index, inplace=True)
            else:
                # TODO:generate agent demographic profiles from the survey data itself by sampling without replacement
                pass
        elif traits_type == "Big5":
            # TODO: code Big5 survey
            sys.exit("big5 survey not yet implemented")
        else:
            print("choose implemented trait type")

        names, genders = get_names_and_genders(num_agents)
        agent_demographics = {
            "age": ages,
            "gender": genders,
            "fake_names": names,  # distinct since survey data typcically anonymized
            "traits": [dict(zip(trait_keys, score, strict=False)) for score in scores],
        }
    return agent_demographics


def get_agent_configs(
    agent_pop_settings,
    candidate_configs,
    active_voter_config,
    malicious_actor_config=None,
    reddit_json_path=None,
):
    if reddit_json_path:
        reddit_rows = read_reddit_agents(reddit_json_path)
        agent_configs_list = []
        count = 0
        for row in reddit_rows[: active_voter_config["num_agents"]]:
            agent = make_agent_from_reddit_row(row)
            count += 1
            agent["role"] = "active_voter"
            agent["goal"] = active_voter_config["goal"]
            agent["candidate_info"] = [cfg["policy_proposals"] for cfg in candidate_configs]
            agent_configs_list.append(agent)
    else:
        agent_demographics = get_trait_demographics(
            agent_pop_settings["trait_type"],
            agent_pop_settings["survey_config_name"],
            active_voter_config["num_agents"],
        )
        demographic_list = ["traits", "gender"]
        agent_configs_list = []
        for ait, name in enumerate(agent_demographics["fake_names"]):
            agent = {}
            agent["name"] = name
            for field in demographic_list:
                agent[field] = agent_demographics[field][ait]
            agent["role"] = "active_voter"
            agent["goal"] = active_voter_config["goal"]
            agent["context"] = f"{agent['name']} is a person who {active_voter_config['context']}"
            agent["candidate_info"] = [cfg["policy_proposals"] for cfg in candidate_configs]
            agent["party"] = ""
            agent["seed_toot"] = ""
            agent_configs_list.append(agent)
    all_agents = candidate_configs + agent_configs_list
    if malicious_actor_config is not None:
        for agent in all_agents:
            if agent["name"] == malicious_actor_config["name"]:
                agent.update(malicious_actor_config)
    return all_agents
