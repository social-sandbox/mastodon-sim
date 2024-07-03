"""Post a message on Mastodon."""

import argparse

from dotenv import find_dotenv, load_dotenv
from mastodon import Mastodon

from mastodon_sim.logging_config import logger
from mastodon_sim.mastodon_ops.env_utils import get_env_variable
from mastodon_sim.mastodon_ops.login import login


def toot(login_user: str, message: str) -> None:
    """Post a message on Mastodon.

    Args:
        login_user (str): The user to log in with.
        message (str): The message to post.
    """
    load_dotenv(find_dotenv())  # Load environment variables from .env file

    try:
        access_token = login(login_user)

        logger.debug(f"{login_user} attempting to post a message...")
        api_base_url = get_env_variable("API_BASE_URL")
        mastodon = Mastodon(access_token=access_token, api_base_url=api_base_url)

        # Post the message
        mastodon.toot(message)
        logger.info(f"{login_user} successfully posted the message.")
    except ValueError as e:
        logger.error(f"Error: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post a message on Mastodon.")
    parser.add_argument("login_user", help="The user to log in with.")
    parser.add_argument("message", help="The message to post.")

    args = parser.parse_args()
    toot(args.login_user, args.message)
