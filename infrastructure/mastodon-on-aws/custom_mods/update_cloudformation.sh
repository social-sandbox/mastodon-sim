#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Configuration
CF_TEMPLATE="../mastodon.yaml"
BACKUP_SUFFIX=$(date +"%Y%m%d_%H%M%S").bak

# Check if image_url.txt exists
if [ ! -f "image_url.txt" ]; then
    echo "Error: image_url.txt not found. Please run build_and_push.sh first."
    exit 1
fi

# Read the new image URL
NEW_IMAGE_URL=$(cat image_url.txt)

# Update the CloudFormation template and create a backup
sed -i."${BACKUP_SUFFIX}" "s|AppImage: '.*'|AppImage: '${NEW_IMAGE_URL}'|g" "${CF_TEMPLATE}"

echo "Updated ${CF_TEMPLATE} with new image URL: ${NEW_IMAGE_URL}"
echo "Backup created: ${CF_TEMPLATE}.${BACKUP_SUFFIX}"
echo "Please review the changes before deploying."
