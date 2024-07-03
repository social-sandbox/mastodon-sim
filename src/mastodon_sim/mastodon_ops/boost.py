"""Boost a post from a user's timeline on Mastodon."""

import argparse

from dotenv import find_dotenv, load_dotenv

from mastodon_sim.logging_config import logger
from mastodon_sim.mastodon_ops.get_client import get_client
from mastodon_sim.mastodon_ops.login import login


def boost_toot(login_user: str, target_user: str, toot_id: str) -> None:
    """Boost (reblog) a post from a user's timeline on Mastodon.

    Args:
        login_user (str): The user to log in with.
        target_user (str): The user whose post will be boosted.
        toot_id (str): The ID of the post to boost.

    Raises
    ------
        ValueError: If there is a problem with the login or boosting the post.
        Exception: If an unexpected error occurs.
    """
    load_dotenv(find_dotenv())  # Load environment variables from .env file

    try:
        access_token = login(login_user)
        mastodon = get_client()
        mastodon.access_token = access_token

        # Boost the post
        logger.debug(f"{login_user} attempting to boost toot {toot_id} from {target_user}...")
        mastodon.status_reblog(toot_id)
        logger.info(f"{login_user} boosted post {toot_id} from {target_user}.")
    except ValueError as e:
        logger.error(f"Error: {e}")
        raise
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Boost a post from a user's timeline on Mastodon.")
    parser.add_argument("login_user", help="The user to log in with.")
    parser.add_argument("target_user", help="The user whose post will be boosted.")
    parser.add_argument("toot_id", help="The ID of the post to boost.")

    args = parser.parse_args()
    try:
        boost_toot(args.login_user, args.target_user, args.toot_id)
        print(f"Successfully boosted post {args.toot_id} from {args.target_user}.")
    except Exception as e:
        print(f"Failed to boost post {args.toot_id} from {args.target_user}. Error: {e}")
