#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Configuration
AWS_REGION="us-east-1"
ECR_REPO_NAME="custom-mastodon"
IMAGE_TAG="latest"
AWS_PROFILE="${AWS_PROFILE:-default}"

# Check if a custom AWS profile is provided
if [ "$1" != "" ]; then
    AWS_PROFILE="$1"
    echo "Using AWS Profile: $AWS_PROFILE"
fi

# Get the account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE)

# Define the ECR repository URL
ECR_REPO_URL="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

# Check if the ECR repository exists, create it if it doesn't
if ! aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region ${AWS_REGION} --profile ${AWS_PROFILE} --query 'repositories[0].repositoryName' --output text 2>/dev/null | grep -q "${ECR_REPO_NAME}"; then
    echo "Creating ECR repository ${ECR_REPO_NAME}..."
    if ! aws ecr create-repository --repository-name "${ECR_REPO_NAME}" --region ${AWS_REGION} --profile ${AWS_PROFILE} >/dev/null 2>&1; then
        echo "Failed to create ECR repository. Please check your AWS permissions and network connection."
        exit 1
    fi
    echo "ECR repository created successfully."
else
    echo "ECR repository ${ECR_REPO_NAME} already exists."
fi

# Authenticate Docker to ECR
echo "Authenticating Docker to ECR..."
aws ecr get-login-password --region ${AWS_REGION} --profile ${AWS_PROFILE} | docker login --username AWS --password-stdin ${ECR_REPO_URL}

# Build the Docker image
echo "Building Docker image..."
docker build -t ${ECR_REPO_NAME}:${IMAGE_TAG} .

# Tag the image for ECR
echo "Tagging image for ECR..."
docker tag ${ECR_REPO_NAME}:${IMAGE_TAG} ${ECR_REPO_URL}:${IMAGE_TAG}

# Push the image to ECR
echo "Pushing image to ECR..."
docker push ${ECR_REPO_URL}:${IMAGE_TAG}

echo "Image successfully built and pushed to ECR"
echo "Image URL: ${ECR_REPO_URL}:${IMAGE_TAG}"

# Output the image URL to a file
echo "${ECR_REPO_URL}:${IMAGE_TAG}" > image_url.txt
