"""Like a post from a user's timeline on Mastodon."""

import argparse

from dotenv import find_dotenv, load_dotenv

from mastodon_sim.logging_config import logger
from mastodon_sim.mastodon_ops.get_client import get_client
from mastodon_sim.mastodon_ops.login import login


def like_toot(login_user: str, target_user: str, toot_id: str) -> None:
    """Like a post from a user's timeline on Mastodon.

    Args:
        login_user (str): The user to log in with.
        target_user (str): The user whose post will be liked.
        toot_id (str): The ID of the post to like.

    Raises
    ------
        ValueError: If there is a problem with the login or liking the post.
        Exception: If an unexpected error occurs.
    """
    load_dotenv(find_dotenv())  # Load environment variables from .env file

    try:
        access_token = login(login_user)
        mastodon = get_client()
        mastodon.access_token = access_token

        # Like the post
        logger.debug(f"{login_user} attempting to like toot {toot_id} from {target_user}...")
        mastodon.status_favourite(toot_id)
        logger.info(f"{login_user} liked post {toot_id} from {target_user}.")
    except ValueError as e:
        logger.error(f"Error: {e}")
        raise
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Like a post from a user's timeline on Mastodon.")
    parser.add_argument("login_user", help="The user to log in with.")
    parser.add_argument("target_user", help="The user whose post will be liked.")
    parser.add_argument("toot_id", help="The ID of the post to like.")

    args = parser.parse_args()
    try:
        like_toot(args.login_user, args.target_user, args.toot_id)
        print(f"Successfully liked post {args.toot_id} from {args.target_user}.")
    except Exception as e:
        print(f"Failed to like post {args.toot_id} from {args.target_user}. Error: {e}")
