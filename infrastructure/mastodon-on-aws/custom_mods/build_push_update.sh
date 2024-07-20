#!/bin/bash

# ./build_push_update.sh austinmwelch5

set -e

# Check if we're in the custom_mods directory
if [[ $(basename "$PWD") != "custom_mods" ]]; then
    echo "Error: This script should be run from the custom_mods directory."
    echo "Current directory: $PWD"
    echo "Please change to the custom_mods directory and try again."
    exit 1
fi

# Run build_and_push.sh
./build_and_push.sh "$@"

# Run update_cloudformation.sh
./update_cloudformation.sh

echo "Build, push, and CloudFormation update completed."
echo "Please review the changes in ../mastodon.yaml before deploying."
