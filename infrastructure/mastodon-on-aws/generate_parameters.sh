#!/bin/bash

# Function to display help menu
show_help() {
  echo "Usage: $0 <domain-name>"
  echo ""
  echo "This script takes a domain name as input, runs the necessary commands inside a Mastodon Docker container,"
  echo "generates secret keys, and stores everything in a file called parameters.json."
  echo ""
  echo "Options:"
  echo "  -h, --help      Show this help message and exit"
  echo ""
  echo "Example:"
  echo "  $0 example.com"
  echo ""
  echo "This will generate a parameters.json file with the following format:"
  echo "["
  echo "  {"
  echo "    \"ParameterKey\": \"SecretKeyBase\","
  echo "    \"ParameterValue\": \"<generated_secret_key_base>\""
  echo "  },"
  echo "  {"
  echo "    \"ParameterKey\": \"DomainName\","
  echo "    \"ParameterValue\": \"example.com\""
  echo "  },"
  echo "  {"
  echo "    \"ParameterKey\": \"OtpSecret\","
  echo "    \"ParameterValue\": \"<generated_otp_secret>\""
  echo "  },"
  echo "  {"
  echo "    \"ParameterKey\": \"VapidPublicKey\","
  echo "    \"ParameterValue\": \"<generated_vapid_public_key>\""
  echo "  },"
  echo "  {"
  echo "    \"ParameterKey\": \"VapidPrivateKey\","
  echo "    \"ParameterValue\": \"<generated_vapid_private_key>\""
  echo "  }"
  echo "]"
}

# Check for help option
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  show_help
  exit 0
fi

# Check if a domain name is provided
if [ -z "$1" ]; then
  echo "Error: Domain name is required."
  show_help
  exit 1
fi

# Assign the domain name to a variable
DOMAIN_NAME=$1

# Start Docker container and run commands inside it
DOCKER_OUTPUT=$(docker run -i --rm ghcr.io/mastodon/mastodon:latest sh -c "
  SECRET_KEY_BASE=\$(bundle exec rake secret)
  OTP_SECRET=\$(bundle exec rake secret)
  VAPID_KEYS=\$(bundle exec rake mastodon:webpush:generate_vapid_key)
  echo \"SECRET_KEY_BASE=\$SECRET_KEY_BASE\"
  echo \"OTP_SECRET=\$OTP_SECRET\"
  echo \"\$VAPID_KEYS\"
")

# Extract values from Docker output
SECRET_KEY_BASE=$(echo "$DOCKER_OUTPUT" | grep 'SECRET_KEY_BASE' | cut -d '=' -f 2)
OTP_SECRET=$(echo "$DOCKER_OUTPUT" | grep 'OTP_SECRET' | cut -d '=' -f 2)
VAPID_PRIVATE_KEY=$(echo "$DOCKER_OUTPUT" | grep 'VAPID_PRIVATE_KEY' | cut -d '=' -f 2)
VAPID_PUBLIC_KEY=$(echo "$DOCKER_OUTPUT" | grep 'VAPID_PUBLIC_KEY' | cut -d '=' -f 2)

# Generate parameters.json
cat <<EOF > parameters.json
[
  {
    "ParameterKey": "SecretKeyBase",
    "ParameterValue": "$SECRET_KEY_BASE"
  },
  {
    "ParameterKey": "DomainName",
    "ParameterValue": "$DOMAIN_NAME"
  },
  {
    "ParameterKey": "OtpSecret",
    "ParameterValue": "$OTP_SECRET"
  },
  {
    "ParameterKey": "VapidPublicKey",
    "ParameterValue": "$VAPID_PUBLIC_KEY"
  },
  {
    "ParameterKey": "VapidPrivateKey",
    "ParameterValue": "$VAPID_PRIVATE_KEY"
  }
]
EOF

echo "parameters.json created successfully."

# Explanation of the parameters:
# SecretKeyBase: Used to encrypt session data, cookies, and other sensitive information in Mastodon.
# DomainName: Specifies the domain on which the Mastodon instance will be hosted.
# OtpSecret: Used for two-factor authentication (2FA) in Mastodon, adding an extra layer of security for user accounts.
# VapidPublicKey: Part of the VAPID (Voluntary Application Server Identification) key pair, used for identifying the server when sending web push notifications.
# VapidPrivateKey: Part of the VAPID key pair, used alongside the VapidPublicKey for securely sending web push notifications.

