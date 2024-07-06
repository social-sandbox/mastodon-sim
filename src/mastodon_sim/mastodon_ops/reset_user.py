"""Reset Mastodon user accounts by deleting all posts, removing likes and boosts, and resetting profile information.

This script provides a comprehensive reset of Mastodon user accounts.

Usage examples:
    1. Reset a single user:
       python reset_user.py user001

    2. Reset multiple users:
       python reset_user.py user001 user002 user003

    3. Reset multiple users without confirmation prompts:
       python reset_user.py user001 user002 user003 --skip-confirm

For more information, use the --help flag:
python reset_user.py --help
"""

import argparse

from dotenv import find_dotenv, load_dotenv

from mastodon_sim.logging_config import logger
from mastodon_sim.mastodon_ops.delete_posts import delete_posts
from mastodon_sim.mastodon_ops.get_client import get_client
from mastodon_sim.mastodon_ops.login import login


def reset_profile(mastodon) -> None:
    """Reset a user's profile information."""
    try:
        mastodon.account_update_credentials(display_name="", note="")
        logger.info("Profile information reset successfully.")
    except Exception as e:
        logger.error(f"Failed to reset profile information: {e!s}")


def remove_favourites_and_boosts(mastodon) -> None:
    """Remove all favourites (likes) and boosts (reblogs) for a user."""
    try:
        # Remove favourites
        favourites = mastodon.favourites()
        for favourite in favourites:
            mastodon.status_unfavourite(favourite["id"])
        logger.info(f"Removed {len(favourites)} favourites.")

        # Remove boosts
        account_id = mastodon.me()["id"]
        statuses = mastodon.account_statuses(account_id)

        # Filter the reblogs (boosts)
        reblogs = [status for status in statuses if status["reblog"]]
        for status in reblogs:
            mastodon.status_unreblog(status["reblog"]["id"])
        logger.info(f"Removed {len(statuses)} boosts.")

    except Exception as e:
        logger.error(f"Error removing favourites and boosts: {e!s}")


def reset_user(login_user: str, skip_confirm: bool = False) -> None:
    """Reset a Mastodon user's account comprehensively.

    Args:
        login_user (str): The user to log in with and reset.
        skip_confirm (bool): Whether to skip the confirmation prompt.
    """
    load_dotenv(find_dotenv())  # Load environment variables from .env file

    try:
        access_token = login(login_user)
        mastodon = get_client()
        mastodon.access_token = access_token

        if not skip_confirm:
            confirm = input(
                f"Are you sure you want to reset the account for {login_user}? "
                f"This will delete all posts, remove all likes and boosts, and reset the profile. "
                f"This action cannot be undone. (y/N): "
            )
            if confirm.lower() != "y":
                logger.info(f"Operation cancelled for user {login_user}.")
                return

        # Delete all posts
        logger.info(f"Deleting all posts for user {login_user}...")
        delete_posts(login_user=login_user, delete_all=True, skip_confirm=True)

        # Remove favourites and boosts
        logger.info(f"Removing favourites and boosts for user {login_user}...")
        remove_favourites_and_boosts(mastodon)

        # Reset profile information
        logger.info(f"Resetting profile information for user {login_user}...")
        reset_profile(mastodon)

        logger.info(f"Comprehensive reset process completed for user: {login_user}")

    except ValueError as e:
        logger.error(f"Error for user {login_user}: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred for user {login_user}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset Mastodon user accounts comprehensively.")
    parser.add_argument("login_users", nargs="+", help="The user(s) to log in with and reset.")
    parser.add_argument("--skip-confirm", action="store_true", help="Skip confirmation prompts.")

    args = parser.parse_args()

    for user in args.login_users:
        reset_user(user, args.skip_confirm)
