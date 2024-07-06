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
from mastodon_sim.mastodon_ops.unfollow import unfollow


def reset_profile(mastodon) -> None:
    """Reset a user's profile information."""
    try:
        mastodon.account_update_credentials(display_name="", note="")
        logger.info("Profile information reset successfully.")
    except Exception as e:
        logger.error(f"Failed to reset profile information: {e!s}")


def unfollow_all_users(mastodon, login_user: str) -> None:
    """Unfollow all users that the current user is following."""
    try:
        # Get the list of users the current user is following
        following = mastodon.account_following(mastodon.me()["id"])
        total_following = len(following)
        unfollowed_count = 0

        logger.info(f"Attempting to unfollow {total_following} users for {login_user}...")

        # Unfollow each user
        for user in following:
            try:
                unfollow(login_user=login_user, unfollow_user=user["acct"])
                unfollowed_count += 1
            except Exception as e:
                logger.warning(f"Failed to unfollow user {user['acct']}: {e}")

        logger.info(
            f"Successfully unfollowed {unfollowed_count} out of {total_following} users for {login_user}."
        )
    except Exception as e:
        logger.error(f"Error in unfollow_all_users for {login_user}: {e}")


def remove_favourites_and_boosts(mastodon) -> None:
    """Remove all favourites (likes) and boosts (reblogs) for a user."""
    try:
        # Remove favourites
        favourites = mastodon.favourites()
        removed_favourites = 0
        for favourite in favourites:
            try:
                mastodon.status_unfavourite(favourite["id"])
                removed_favourites += 1
            except Exception as e:
                logger.warning(f"Failed to remove favourite {favourite['id']}: {e}")
        logger.info(f"Removed {removed_favourites} out of {len(favourites)} favourites.")

        # Remove boosts
        account_id = mastodon.me()["id"]
        statuses = mastodon.account_statuses(account_id)
        reblogs = [status for status in statuses if status.get("reblog")]
        removed_boosts = 0
        for status in reblogs:
            try:
                mastodon.status_unreblog(status["reblog"]["id"])
                removed_boosts += 1
            except Exception as e:
                logger.warning(f"Failed to remove boost {status['id']}: {e}")
        logger.info(f"Removed {removed_boosts} out of {len(reblogs)} boosts.")

    except Exception as e:
        logger.error(f"Error removing favourites and boosts: {e}")


def reset_user(login_user: str, skip_confirm: bool = False) -> None:
    """Reset a Mastodon user's account comprehensively."""
    load_dotenv(find_dotenv())  # Load environment variables from .env file

    try:
        access_token = login(login_user)
        mastodon = get_client()
        mastodon.access_token = access_token

        if not skip_confirm:
            confirm = input(
                f"Are you sure you want to reset the account for {login_user}? "
                f"This will delete all posts, remove all likes and boosts, unfollow all users, "
                f"and reset the profile. This action cannot be undone. (y/N): "
            )
            if confirm.lower() != "y":
                logger.info(f"Operation cancelled for user {login_user}.")
                return

        logger.info(f"Starting comprehensive reset process for user: {login_user}")

        # Delete all posts
        logger.info(f"Deleting all posts for user {login_user}...")
        delete_posts(login_user=login_user, delete_all=True, skip_confirm=True)

        # Remove favourites and boosts
        logger.info(f"Removing favourites and boosts for user {login_user}...")
        remove_favourites_and_boosts(mastodon)

        # Unfollow all users
        logger.info(f"Unfollowing all users for {login_user}...")
        unfollow_all_users(mastodon, login_user)

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
