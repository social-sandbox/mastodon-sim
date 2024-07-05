#!/bin/bash

# Default values
S3_BUCKET=""
AWS_PROFILE=""
CFN_MODULES_PATH="node_modules/@cfn-modules"
CLEAR_BUCKET=false

# Function to display help menu
show_help() {
    echo "Usage: $0 -b <s3-bucket> -p <aws-profile> [-c]"
    echo ""
    echo "This script packages CloudFormation modules and uploads them to an S3 bucket."
    echo ""
    echo "Options:"
    echo "  -b, --bucket       S3 bucket to upload to (format: bucket-name, without s3:// prefix)"
    echo "  -p, --profile      AWS profile to use"
    echo "  -c, --clear        Optional flag to clear the S3 bucket before uploading (default: off)"
    echo "  -h, --help         Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 -b deploy-mastodon-aws -p austinmw -c"
}

# Function to check if a command succeeded
check_command() {
    if [ $? -ne 0 ]; then
        echo "Error: $1"
        exit 1
    fi
}

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -b|--bucket) S3_BUCKET="$2"; shift ;;
        -p|--profile) AWS_PROFILE="$2"; shift ;;
        -c|--clear) CLEAR_BUCKET=true ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown parameter passed: $1"; show_help; exit 1 ;;
    esac
    shift
done

# Check if required parameters are provided
if [ -z "$S3_BUCKET" ] || [ -z "$AWS_PROFILE" ]; then
    echo "Error: S3 bucket and AWS profile are required."
    show_help
    exit 1
fi

# Clear the S3 bucket if the clear flag is set
if $CLEAR_BUCKET; then
    echo "Clearing contents of s3://$S3_BUCKET"
    aws s3 rm s3://$S3_BUCKET --recursive --profile $AWS_PROFILE
    check_command "Failed to clear S3 bucket"
fi

# Function to upload a directory to S3
upload_directory() {
    local dir=$1
    local s3_path=$2
    echo "Uploading $dir to $s3_path"
    aws s3 sync "$dir" "$s3_path" --profile $AWS_PROFILE
    check_command "Failed to upload $dir"
}

# Upload the entire node_modules/@cfn-modules directory
upload_directory "$CFN_MODULES_PATH" "s3://$S3_BUCKET/node_modules/@cfn-modules"

# Run the CloudFormation package command
echo "Packaging CloudFormation template"
aws cloudformation package \
  --template-file mastodon.yaml \
  --s3-bucket $S3_BUCKET \
  --s3-prefix "node_modules" \
  --output-template-file packaged.yml \
  --profile $AWS_PROFILE
check_command "CloudFormation packaging failed"

echo "Packaging complete. Output template: packaged.yml"

