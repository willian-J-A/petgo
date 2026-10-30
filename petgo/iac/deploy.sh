#!/usr/bin/env bash
# Deploy do PetGo na AWS com um unico comando (CloudFormation).
#
# Uso:
#   bash iac/deploy.sh
#   STACK_NAME=petgo REGION=us-east-1 ALLOWED_CIDR=0.0.0.0/0 bash iac/deploy.sh
set -euo pipefail

STACK_NAME="${STACK_NAME:-petgo}"
REGION="${REGION:-us-east-1}"
REPO_URL="${REPO_URL:-https://github.com/willian-J-A/petgo.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
APP_SUBDIR="${APP_SUBDIR:-petgo}"
APP_PORT="${APP_PORT:-8080}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.small}"
ALLOWED_CIDR="${ALLOWED_CIDR:-0.0.0.0/0}"
ENABLE_RDP="${ENABLE_RDP:-false}"
KEY_NAME="${KEY_NAME:-}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${DIR}/petgo-cfn.yaml"

echo "==> Validando template"
aws cloudformation validate-template --template-body "file://${TEMPLATE}" --region "${REGION}" >/dev/null

echo "==> Deploy do stack '${STACK_NAME}' em ${REGION} (pode levar ~10-15 min)"
aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --region "${REGION}" \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    "RepoUrl=${REPO_URL}" \
    "RepoBranch=${REPO_BRANCH}" \
    "AppSubdir=${APP_SUBDIR}" \
    "AppPort=${APP_PORT}" \
    "InstanceType=${INSTANCE_TYPE}" \
    "AllowedCidr=${ALLOWED_CIDR}" \
    "EnableRdp=${ENABLE_RDP}" \
    "KeyName=${KEY_NAME}"

echo ""
echo "==> Deploy concluido. Saidas do stack:"
aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${REGION}" \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table

URL=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='AccessUrl'].OutputValue" --output text)
echo ""
echo "Acesse: ${URL}"
