#!/usr/bin/env bash
set -euo pipefail

export LANG="${LANG:-en_US.UTF-8}"
export DOCKER_BUILDKIT=1

MODULE_NAME="${1:-app}"
ENVIRONMENT="${2:-dev}"
VERSION="${3:-latest}"
BRANCH_NAME="${4:-unknown}"
DEPLOYED_BY="${5:-unknown}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-000000000000}"
ECR_REGISTRY="${ECR_REGISTRY:-${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com}"
GIT_REPOSITORY="${GIT_REPOSITORY:-git@example.com:organization/repository.git}"
KUBECONFIG_PATH="${KUBECONFIG_PATH:-${HOME}/.kube/config}"
WORK_ROOT="${WORK_ROOT:-${HOME}/deployments}"
K8S_NAMESPACE="${K8S_NAMESPACE:-default}"
K8S_DEPLOYMENT_NAME="${K8S_DEPLOYMENT_NAME:-app}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-apps}"
REGISTRY_SECRET="${REGISTRY_SECRET:-registry-credentials}"
CONFIG_SECRET="${CONFIG_SECRET:-app-config}"
DOCKER_CONFIG_PATH="${DOCKER_CONFIG_PATH:-${HOME}/.docker/config.json}"
DEPLOY_TIMEOUT="${DEPLOY_TIMEOUT:-120s}"

APP_NAME="${MODULE_NAME//_/-}"
REPOSITORY_PATH="${WORK_ROOT}/${ENVIRONMENT}/${MODULE_NAME}"
IMAGE_REPOSITORY="${IMAGE_NAMESPACE}/${APP_NAME}"
IMAGE="${ECR_REGISTRY}/${IMAGE_REPOSITORY}:${VERSION}"
MANIFEST_PATH="${REPOSITORY_PATH}/deploy/mercury/k8s.yaml"
DOCKERFILE_PATH="${REPOSITORY_PATH}/deploy/mercury/Dockerfile"

log() {
  printf '\n=== %s ===\n' "$1"
}

initialize_environment() {
  log "Authenticating deployment environment"
  aws ecr get-login-password --region "${AWS_REGION}" |
    docker login --username AWS --password-stdin "${ECR_REGISTRY}"

  kubectl --namespace "${K8S_NAMESPACE}" \
    create secret generic "${REGISTRY_SECRET}" \
    --from-file=".dockerconfigjson=${DOCKER_CONFIG_PATH}" \
    --type=kubernetes.io/dockerconfigjson \
    --dry-run=client \
    --output=yaml |
    kubectl apply --kubeconfig="${KUBECONFIG_PATH}" --filename=-
}

update_source() {
  log "Updating source"
  mkdir -p "$(dirname "${REPOSITORY_PATH}")"

  if [[ ! -d "${REPOSITORY_PATH}/.git" ]]; then
    git clone "${GIT_REPOSITORY}" "${REPOSITORY_PATH}"
  fi

  git -C "${REPOSITORY_PATH}" fetch --all --tags
  git -C "${REPOSITORY_PATH}" reset --hard "${VERSION}"
}

build_and_push_image() {
  log "Building and pushing image"
  docker build \
    --tag "${IMAGE}" \
    --file "${DOCKERFILE_PATH}" \
    "${REPOSITORY_PATH}"
  docker push "${IMAGE}"
}

deploy() {
  log "Applying Kubernetes manifest"
  sed \
    -e "s#namespace: default#namespace: ${K8S_NAMESPACE}#g" \
    -e "s#image: .*:latest#image: ${IMAGE}#g" \
    -e "s#secretName: app-config#secretName: ${CONFIG_SECRET}#g" \
    "${MANIFEST_PATH}" |
    kubectl apply --kubeconfig="${KUBECONFIG_PATH}" --filename=-

  kubectl --namespace "${K8S_NAMESPACE}" \
    rollout status "deployment/${K8S_DEPLOYMENT_NAME}" \
    --kubeconfig="${KUBECONFIG_PATH}" \
    --timeout="${DEPLOY_TIMEOUT}"
}

cleanup_image() {
  docker image rm --force "${IMAGE}" >/dev/null 2>&1 || true
}

printf 'Environment: %s\nApplication: %s\nBranch: %s\nVersion: %s\nDeployed by: %s\n' \
  "${ENVIRONMENT}" "${APP_NAME}" "${BRANCH_NAME}" "${VERSION}" "${DEPLOYED_BY}"

initialize_environment
update_source
build_and_push_image
deploy
cleanup_image
