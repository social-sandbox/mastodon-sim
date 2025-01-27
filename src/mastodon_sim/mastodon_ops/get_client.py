"""Provides utility functions for Mastodon client."""

from mastodon import Mastodon
from mastodon.errors import MastodonError

from mastodon_sim.logging_config import logger
from mastodon_sim.mastodon_ops.env_utils import get_env_variable


def get_client(access_token: str | None = None) -> Mastodon:
    """
    Get the Mastodon client using environment variables for configuration.

    Returns
    -------
        Mastodon: An instance of the Mastodon client.
    """
    try:
        api_base_url = get_env_variable("API_BASE_URL")
        client_id = get_env_variable("MASTODON_CLIENT_ID")
        client_secret = get_env_variable("MASTODON_CLIENT_SECRET")

        mastodon = Mastodon(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            api_base_url=api_base_url,
            version_check_mode="none",
            ratelimit_method="wait",
        )
        logger.debug("Successfully created Mastodon client.")
        return mastodon
    except MastodonError as e:
        logger.exception(f"An error occurred while creating the Mastodon client: {e}")
        raise
    except ValueError as e:
        logger.error(f"Environment variable error: {e}")
        raise
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        raise
