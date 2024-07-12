[![CI](https://github.com/social-sandbox/mastodon-sim/actions/workflows/test.yml/badge.svg)](https://github.com/social-sandbox/mastodon-sim/actions/workflows/test.yml)
[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/social-sandbox/mastodon-sim)

# Mastodon Social Simulation

Generative Agent simulation of a Mastodon social network

> [!WARNING]
> **Work in Progress**
>
> This README is currently under development. The information provided here may be incomplete, subject to change, and may not yet reflect the current state of the codebase. We appreciate your patience as we work on improving our documentation to accurately represent the project.
>
> **Last updated:** July 06, 2024

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
