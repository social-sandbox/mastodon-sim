News_agent branch
[![CI](https://github.com/social-sandbox/mastodon-sim/actions/workflows/test.yml/badge.svg)](https://github.com/social-sandbox/mastodon-sim/actions/workflows/test.yml)
[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/social-sandbox/mastodon-sim)

# Mastodon Social Simulation

Yaml(_i.e._ fully text)- configurable generative agent simulation of social media using the [Concordia framework](https://github.com/google-deepmind/concordia).
- 2024 NeurIPS Workshop Paper: [http://arxiv.org/abs/2410.13915](http://arxiv.org/abs/2410.13915).
- 2025 demo paper (in review).

## Code Overview

### Files
- `mastodon-sim/src/sim` is the multi-LLM-agent simulation library
- `mastodon-sim/src/mastodon_sim` is the library of tools for simulating and deploying the (in this case Mastodon) social media server, as well as the simulated experience technology for the agents needed to access it.
- `mastodon-sim/src/sim/main.py` runs the simulation orchestrated in `config.yaml` located in `mastodon-sim/conf/`and generated by running `mastodon-sim/src/sim/gen_configs.py`

### Configuration
We provide an example application that simulates an election simulation. Example-specific configuration code for this example is located in `mastodon-sim/examples/election`.
There are 4 yaml files listed in `config.yaml` that configure the simulation. Here they are, along with what they consist of in the case of the election example:

| config file | description | election example |
| ----------- | ----------- | ---------------- |
| `soc_sys.yaml` | detailed structured information about the social system: the shared knowledge and social context of the agents. | We detail the fictitious town in which the election occurs as well as the social context that the agents should adhere. |
| `agents.yaml` | Use `base_agent.py` or make custom agents in `agent_lib` by adding custom components. | We made 3 custom agents: `voter.py`, `candidate.py`, and `malicious.py` |
| `probes.yaml` | Add custom query types (with formatting from dynamic values) to a library and specify them in `probes.yaml`. We currently use this function to deploy longitudinal surveys on the agent population. | We made 3 types: `Favorability`, `VotePreference`, `IntentToVote`. We formed two versions of the first two types, one for each candidate. |
| `sim.yaml` | This contains simulator attributes like the language model and how long to run the simulation for. | N/A |

`sim.yaml` does not have example-specific attributes and is specified directly in `mastodon-sim/src/sim/gen_configs.py`. To facilitate writing the 3 other, example-specific config files, we made a script `mastodon-sim/examples/election/gen_configs.py` that is called from `mastodon-sim/src/sim/gen_configs.py`. It takes `sim.yaml` as input and outputs the other three configs.

We use the Hydra package to manage config files, run simulations, and log output. See the [hydra documentation](https://hydra.cc/docs/intro/) for more details. One simple use of hydra is to override default parameter values by including them in the command line. More structured experiments can be made with customized yaml files.

### Output
Simulation output is a set of files located in the respective examples folder, here `mastodon-sim/examples/election/outputs/run_name/` where `run_name` is a parameter in `sim.yaml`.

| Output file | Description |
| ----------- | ----------- |
| `events.json` | stores agent plans, actions, and probe results. |
| `prompts_and_responses.jsonl` | stores language model prompts and responses |
| `.hydra/config.yaml` | stores all config information into a single yaml file |

`mastodon-sim/src/sim/analysis_utils/dashboard-withthoughts.py` is a dashboard script that loads a browser-based dashboard from which output data files are loaded in and automated analytics including social networks are presented for the user to analyze the results. Here is a snapshot:

![alt text](https://github.com/social-sandbox/mastodon-sim/blob/main/docs/img/dashboard_snapshot.png?raw=true)

## Detailed file structure:
<pre>
mastodon-sim
├── conf
│   ├── config.yaml
│   ├── sim
|   |   └── election_sim.yaml
│   ├── agents
|   |   └── election_agents.yaml
|   ├── soc_sys
|   |   └── election_soc_sys.yaml
|   └── probes
|       └── election_probes.yaml
├── examples
│   └── election
│       ├── gen_configs.py
│       ├── config_utils
│       │   └── agent_query_lib.py
│       ├── input
│       │   ├── news_data
│       │   │   ├── news_agent_utils.py
│       │   │   ├── news_processing.py
│       │   │   └── write_newsfile_from_filesheadlines.py
│       │   └── personas
│       │       ├── Post-processing_Cleaning.py
│       │       ├── Pre-processing_Cleaning.py
│       │       ├── Pre-scraping_Extraction.py
│       │       ├── Ranking_Interaction.py
│       │       ├── Reddit_Persona_Generation.py
│       │       └── Top-k_Extraction.py
│       ├── notebooks
│       │   ├── basic_output_processing.ipynb
│       │   └── basic_sim.ipynb
│       ├── agent_lib
│       |   ├── candidate.py
│       |   ├── malicious.py
│       |   └── voter.py
|       └── outputs
|           └── run_name
|               ├── .hydra
|               |   └── config.yaml
|               ├── run_name_date_time_events.jsonl
|               ├── run_name_date_time_prompts_and_responses.jsonl
|               └── run_name_date_time.log
└── src
    ├── mastodon_sim
    │   ├── concordia
    │   │   └── components
    │   │       ├── apps.py
    │   │       ├── logging.py
    │   │       ├── scene.py
    │   │       └── triggering.py
    │   ├── mastodon_ops
    │   │   ├── block.py
    │   │   ├── boost.py
    │   │   ├── create_app.py
    │   │   ├── create_env_file.py
    │   │   ├── delete_posts.py
    │   │   ├── env_utils.py
    │   │   ├── follow.py
    │   │   ├── get_account_id.py
    │   │   ├── get_client.py
    │   │   ├── like.py
    │   │   ├── login.py
    │   │   ├── mute.py
    │   │   ├── new_app.py
    │   │   ├── notifications.py
    │   │   ├── post_status.py
    │   │   ├── read_bio.py
    │   │   ├── reset_users.py
    │   │   ├── timeline.py
    │   │   ├── toot.py
    │   │   ├── unblock.py
    │   │   ├── unfollow.py
    │   │   ├── unmute.py
    │   │   └── update_bio.py
    │   └── mastodon_utils
    │       ├── account_ids.py
    │       ├── create_app.py
    │       ├── get_users_from_env.py
    │       └── graphs.py
    └── sim
        ├── main.py
        ├── gen_configs.py
        ├── agent_utils
        │   ├── base_agent.py
        │   ├── exogenenous_agent.py
        │   └── online_gamemaster.py
        ├── analysis_utils
        |   ├── output_proc_utils.py
        │   └── dashboard.py
        └── sim_utils
            ├── agent_speech_utils.py
            ├── concordia_utils.py
            ├── media_utils.py
            └── misc_sim_utils.py
</pre>
<!--
## Hidden Section

## Installing

To install this package, run:

```sh
pip install mastodon-sim
```

-->

## Development Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/social-sandbox/mastodon-sim.git
    cd mastodon-sim
    ```

2. Install Poetry (for managing dependencies):

    ```sh
    curl -sSL https://install.python-poetry.org | python3 -
    ```

    Note that poetry offers several [alternative installation methods](<https://python-poetry.org/docs/#installation}>).

3. Configure Poetry to create virtual environments within the project directory:

    ```sh
    poetry config virtualenvs.in-project true
    ```

4. Install the dependencies:

    ```sh
    poetry install
    ```

## Environment Variables

The application relies on a `.env` file to manage sensitive information and configuration settings. This file should be placed in the root directory of your project and contain key-value pairs for required environment variables. The `dotenv` library is used to load these variables into the environment.

### Example `.env` File

Below is an example of what your `.env` file might look like. Make sure to replace the placeholder values with your actual configuration. Note that sensitive values like client IDs, secrets, and passwords are masked for security.

```dotenv
# Mastodon API base URL
API_BASE_URL=https://<domain_name>

# Mastodon client credentials
MASTODON_CLIENT_ID=*************************0
MASTODON_CLIENT_SECRET=*********************************o

# Email prefix for user accounts
EMAIL_PREFIX=<email_prefix>

# Bot user passwords
USER001_PASSWORD=***************************5
USER002_PASSWORD=***************************8
```

<!--
## Hidden Section

## Using

To view the CLI help information, run:

```sh
mastodon-sim --help
```

-->

### Running Experiments

- See `mastodon-sim/infrastructure/mastodon-on-aws/README.md` for Mastodon server deployment instructions.
- See `mastodon-sim/notebooks` to run experiments after deploying the server.
