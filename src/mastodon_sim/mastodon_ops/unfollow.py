"""Unfollow a user on Mastodon."""

import argparse

from dotenv import find_dotenv, load_dotenv
from mastodon import Mastodon

from mastodon_sim.logging_config import logger
from mastodon_sim.mastodon_ops.env_utils import get_env_variable
from mastodon_sim.mastodon_ops.login import login


def unfollow(login_user: str, unfollow_user: str) -> None:
    """Unfollow a user on Mastodon.

    Args:
        login_user (str): The user to log in with.
        unfollow_user (str): The user to unfollow.
    """
    load_dotenv(find_dotenv())  # Load environment variables from .env file

    try:
        access_token = login(login_user)

        logger.debug(f"{login_user} attempting to unfollow {unfollow_user}...")
        api_base_url = get_env_variable("API_BASE_URL")
        mastodon = Mastodon(access_token=access_token, api_base_url=api_base_url)

        # Search for the user to unfollow and get their ID
        account = mastodon.account_search(unfollow_user, limit=1)
        if account:
            mastodon.account_unfollow(account[0]["id"])
            logger.info(f"{login_user} has unfollowed {unfollow_user}.")
        else:
            logger.warning(f"User {unfollow_user} not found.")
    except ValueError as e:
        logger.error(f"Error: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unfollow a user on Mastodon.")
    parser.add_argument("login_user", help="The user to log in with.")
    parser.add_argument("unfollow_user", help="The user to unfollow.")

    args = parser.parse_args()
    unfollow(args.login_user, args.unfollow_user)
