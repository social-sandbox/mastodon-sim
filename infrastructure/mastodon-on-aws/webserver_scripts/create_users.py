#!/usr/bin python3
"""
create_users.py - Mastodon User Creator Script.

This script automates the process of creating and approving multiple user accounts
for a Mastodon instance using the `tootctl` command-line tool.

Example usage:
    python3 create_users.py testemail -n 3 --dry-run
    This will simulate creating 3 users without actually making any changes

    python3 create_users.py youremail -n 5
    This will create 5 users with email addresses like youremail+user0001@gmail.com

    python3 create_users.py youremail -n 5 --creds-file custom_creds.txt
    This will create 5 users and save the credentials to custom_creds.txt

Note:
    After running this script, the generated user credentials can be copied to your
    .env file. This allows these users to be used with the Mastodon API operations.

    Example of how to add credentials to .env:
    USER0001_PASSWORD=generated_password_for_user0001
    USER0002_PASSWORD=generated_password_for_user0002
    ...
"""

import argparse
import os
import re
import subprocess
import sys

from loguru import logger
from tqdm import tqdm


def create_user(username: str, email: str, dry_run: bool = False) -> tuple[bool, str, str]:
    """
    Create a new Mastodon user account.

    Args:
        username (str): The username for the new account.
        email (str): The email address for the new account.
        dry_run (bool): If True, simulate the action without making changes.

    Returns
    -------
        Tuple[bool, str, str]: A tuple containing a success flag,
                               the generated password (or error message),
                               and the full command output.
    """
    logger.info(f"Creating user: {username}")
    logger.info(f"Using email: {email}")

    cmd = [
        "bin/tootctl",
        "accounts",
        "create",
        username,
        "--email",
        email,
        "--confirmed",
    ]

    success = False
    password = ""
    output = ""

    if dry_run:
        logger.info(f"Dry run: Would execute command: {' '.join(cmd)}")
        success, password, output = True, "dry_run_password", "Dry run output"
    else:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            success, password = parse_output(output, username)
        except subprocess.CalledProcessError as e:
            output = e.output
            logger.error(f"Failed to create user {username}")
            success = False

        # If the initial attempt failed due to "taken" error, try again with --reattach --force
        if not success and "taken" in output:
            logger.warning(
                f"User {username} or email already exists. Trying with --reattach --force options."
            )
            cmd.extend(["--reattach", "--force"])
            try:
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
                success, password = parse_output(output, username)
            except subprocess.CalledProcessError as e:
                output = e.output
                logger.error(f"Failed to create user {username} even with --reattach --force")
                success = False

    return success, password, output


def parse_output(output: str, username: str) -> tuple[bool, str]:
    """
    Parse the output of the tootctl command.

    Args:
        output (str): The command output to parse.
        username (str): The username being created.

    Returns
    -------
        Tuple[bool, str]: A tuple containing a success flag and the password (if found).
    """
    if "OK" in output:
        password_match = re.search(r"New password: (\S+)", output)
        if password_match:
            password = password_match.group(1)
            logger.success(f"User {username} created successfully")
            logger.info(f"Generated password for {username}: {password}")
            return True, password
        logger.error(f"User created but could not extract password for {username}")
        return False, "password_not_found"
    if "taken" in output:
        logger.warning(f"User {username} or email already exists.")
        return False, ""
    logger.error(f"Unexpected output for {username}")
    return False, ""


def approve_user(username: str, dry_run: bool = False) -> tuple[bool, str]:
    """
    Approve a Mastodon user account.

    Args:
        username (str): The username of the account to approve.
        dry_run (bool): If True, simulate the action without making changes.

    Returns
    -------
        Tuple[bool, str]: A tuple containing a success flag and the command output.
    """
    if dry_run:
        logger.info(f"Dry run: Would approve user {username}")
        return True, "Dry run: Would approve user"

    try:
        output = subprocess.check_output(
            ["bin/tootctl", "accounts", "approve", username], stderr=subprocess.STDOUT, text=True
        )
        logger.success(f"User {username} approved successfully")
        return True, output
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to approve user {username}")
        return False, e.output


def main(email_prefix: str, num_users: int, dry_run: bool, creds_file: str):
    """
    Create and approve Mastodon user accounts.

    Args:
        email_prefix (str): The prefix to use for email addresses.
        num_users (int): The number of users to create.
        dry_run (bool): If True, simulate the actions without making changes.
        creds_file (str): The file to save user credentials.
    """
    if os.path.exists(creds_file) and not dry_run:
        os.remove(creds_file)

    # Create a tqdm progress bar
    with tqdm(total=num_users, desc="Creating users", unit="user") as pbar:
        for i in range(1, num_users + 1):
            username = f"user{i:04d}"
            email = f"{email_prefix}+{username}@gmail.com"

            success, password, output = create_user(username, email, dry_run)
            if not success:
                logger.error(f"User creation failed for {username}. Command output:")
                logger.error(output)
                logger.error("Stopping the process.")
                sys.exit(1)

            approve_success, approve_output = approve_user(username, dry_run)
            if not approve_success:
                logger.error(f"User approval failed for {username}. Command output:")
                logger.error(approve_output)
                logger.error("Stopping the process.")
                sys.exit(1)

            if not dry_run:
                with open(creds_file, "a") as f:
                    f.write(f"USER{i:04d}_PASSWORD={password}\n")

            # Update the progress bar
            pbar.update(1)
            pbar.set_postfix({"Last User": username})

    if not dry_run:
        logger.info(f"User creation completed. Credentials saved in {creds_file}")
    else:
        logger.info("Dry run completed. No changes were made.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Mastodon user accounts")
    parser.add_argument(
        "email_prefix", type=str, help="Email prefix for user accounts (e.g., youremail)"
    )
    parser.add_argument(
        "-n", "--num-users", type=int, default=5, help="Number of users to create (default: 5)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate the actions without making any changes"
    )
    parser.add_argument(
        "--creds-file",
        type=str,
        default="user_credentials.txt",
        help="File to save user credentials (default: user_credentials.txt)",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    main(args.email_prefix, args.num_users, args.dry_run, args.creds_file)
