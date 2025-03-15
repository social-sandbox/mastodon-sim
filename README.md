News_agent branch
[![CI](https://github.com/social-sandbox/mastodon-sim/actions/workflows/test.yml/badge.svg)](https://github.com/social-sandbox/mastodon-sim/actions/workflows/test.yml)
[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/social-sandbox/mastodon-sim)

# Mastodon Social Simulation

Yaml (_i.e._ fully text configurable) generative agent simulation of social media using the [Concordia framework](https://github.com/google-deepmind/concordia).
- 2024 NeurIPS Workshop Paper: [http://arxiv.org/abs/2410.13915](http://arxiv.org/abs/2410.13915).
- 2025 demo paper (in review)

## File structure
Overview
- `mastodon-sim/src/sim` has multi-LLM-agent simulation code
- `mastodon-sim/src/mastodon_sim` has simulated and deployed social media server code and the simulated experience technology for the agents needed to access it.
- `mastodon-sim/examples/election` has code that configures an election simulation as an example
- `conf` contains a nested set of configuration files that set all the options for the simulation
  - `sim.yaml`
    - `agents.yaml`
    - `soc_sys.yaml`
    - `probes.yaml`
- `mastodon-sim/src/sim/main.py` runs the simulation configured in `conf`, and also optionally writes `conf` by defining `sim.yaml` and sending it to `mastodon-sim/examples/election/gen_config.py`, which generates the example specific  `agents.yaml`, `soc_sys.yaml`, and `probes.yaml` config files.

Detailed structure:
<pre>
mastodon-sim
├── conf
│   ├── election.yaml
|   └── election
│       ├── agents.yaml
|       ├── soc_sys.yaml
|       └── probes.yaml
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
|       └── output
|           └── run_name_date_time
|               ├── run_name_date_time.yaml
|               ├── run_name_date_time_events.jsonl
|               ├── run_name_date_time_prompts_and_responses.jsonl
|               └── run_name_date_time_shell_output.log
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
