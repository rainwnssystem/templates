#!/bin/bash
set -e

ACCOUNT_ID='200148130345'
AWS_REGION='us-east-1'
ECR_REPO_NAME='wsi-product'

cd /opt/wsi-product

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
sleep 3
docker pull $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest
docker run -dp 8080:8080 --name product $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest