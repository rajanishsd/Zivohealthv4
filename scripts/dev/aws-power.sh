#!/usr/bin/env bash
set -euo pipefail

# aws-power.sh — Stop/start EC2, RDS instances, and RDS clusters by tag or IDs.
# Requirements:
# - AWS CLI v2 installed and configured (credentials + region)
# - Permissions: ec2:DescribeInstances, ec2:StartInstances, ec2:StopInstances,
#   rds:DescribeDBInstances, rds:StartDBInstance, rds:StopDBInstance,
#   rds:DescribeDBClusters, rds:StartDBCluster, rds:StopDBCluster,
#   tag:GetResources (resourcegroupstaggingapi:GetResources)

usage() {
  cat <<EOF
Usage:
  $(basename "$0") start|stop [--region REGION] [--profile PROFILE]
                         [--tag KEY=VALUE]
                         [--ec2-ids i-123,i-456]
                         [--rds-instance-ids db1,db2]
                         [--rds-cluster-ids cluster1,cluster2]
                         [--no-wait]

Notes:
- Use --tag to select all EC2/RDS (instances/clusters) sharing a tag.
- You can mix --tag with explicit ids; duplicates are de-duped.
- If neither --tag nor any ids are provided, the script exits safely.

Examples:
  $(basename "$0") stop --tag AutoSchedule=true
  $(basename "$0") start --region us-east-1 --profile prod --tag Environment=Dev
  $(basename "$0") stop --ec2-ids i-abc123,i-def456 --rds-instance-ids mydb1
  $(basename "$0") start --rds-cluster-ids aurora-prod
EOF
}

ACTION="${1:-}"
[[ "${ACTION}" == "start" || "${ACTION}" == "stop" ]] || { usage; exit 1; }
shift || true

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
PROFILE=""
TAG_KEY=""
TAG_VALUE=""
EC2_IDS_CSV=""
RDS_INSTANCE_IDS_CSV=""
RDS_CLUSTER_IDS_CSV=""
NO_WAIT="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2;;
    --profile) PROFILE="$2"; shift 2;;
    --tag)
      IFS='=' read -r TAG_KEY TAG_VALUE <<<"$2" || true
      if [[ -z "${TAG_KEY}" || -z "${TAG_VALUE}" ]]; then
        echo "Invalid --tag. Use --tag Key=Value" >&2; exit 1
      fi
      shift 2;;
    --ec2-ids) EC2_IDS_CSV="$2"; shift 2;;
    --rds-instance-ids) RDS_INSTANCE_IDS_CSV="$2"; shift 2;;
    --rds-cluster-ids) RDS_CLUSTER_IDS_CSV="$2"; shift 2;;
    --no-wait) NO_WAIT="true"; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

# Preflight: AWS CLI presence
if ! command -v aws >/dev/null 2>&1; then
  echo "Error: aws CLI not found. Install AWS CLI v2 and configure credentials." >&2
  exit 2
fi

# If region not provided via args or env, try AWS config default (optionally per profile)
if [[ -z "${REGION}" ]]; then
  if [[ -n "${PROFILE}" ]]; then
    cfg_region=$(aws --profile "${PROFILE}" configure get region 2>/dev/null || true)
  else
    cfg_region=$(aws configure get region 2>/dev/null || true)
  fi
  if [[ -n "${cfg_region}" ]]; then
    REGION="${cfg_region}"
  fi
fi

# Require region to avoid AWS CLI failures later
if [[ -z "${REGION}" ]]; then
  echo "Error: AWS region not set. Use --region or export AWS_REGION (or set a default with 'aws configure')." >&2
  exit 2
fi

AWS_BASE_ARGS=()
[[ -n "${REGION}" ]] && AWS_BASE_ARGS+=(--region "${REGION}")
[[ -n "${PROFILE}" ]] && AWS_BASE_ARGS+=(--profile "${PROFILE}")

# Safe AWS wrapper to avoid nounset issues with empty arrays on bash 3.2
awscli() {
  if [[ ${#AWS_BASE_ARGS[@]:-0} -gt 0 ]]; then
    aws "${AWS_BASE_ARGS[@]}" "$@"
  else
    aws "$@"
  fi
}

# Preflight: verify credentials by calling STS
if ! awscli sts get-caller-identity >/dev/null 2>&1; then
  echo "Error: AWS credentials not found or invalid for ${PROFILE:-default} in ${REGION}. Run 'aws configure' or set your SSO/session." >&2
  exit 2
fi

# Collect resources by tag via Resource Groups Tagging API
EC2_IDS_FROM_TAG=()
RDS_INSTANCE_IDS_FROM_TAG=()
RDS_CLUSTER_IDS_FROM_TAG=()

if [[ -n "${TAG_KEY}" && -n "${TAG_VALUE}" ]]; then
  echo "Discovering resources by tag ${TAG_KEY}=${TAG_VALUE} ..."
  if ARNS=$(awscli resourcegroupstaggingapi get-resources \
      --resource-type-filters ec2:instance rds:db rds:cluster \
      --tag-filters "Key=${TAG_KEY},Values=${TAG_VALUE}" \
      --query 'ResourceTagMappingList[].ResourceARN' \
      --output text 2>/dev/null); then
      :
  else
      echo "Warning: failed to discover resources by tag (insufficient permissions or invalid tag)." >&2
      ARNS=""
  fi

  for ARN in ${ARNS:-}; do
    # EC2 instance ARN: arn:aws:ec2:REGION:ACCOUNT:instance/i-xxxx
    if [[ "${ARN}" == arn:aws:ec2:*:*:instance/* ]]; then
      EC2_IDS_FROM_TAG+=("${ARN##*/}")
      continue
    fi
    # RDS instance ARN: arn:aws:rds:REGION:ACCOUNT:db:identifier
    if [[ "${ARN}" == arn:aws:rds:*:*:db:* ]]; then
      RDS_INSTANCE_IDS_FROM_TAG+=("${ARN##*:}")
      continue
    fi
    # RDS cluster ARN: arn:aws:rds:REGION:ACCOUNT:cluster:identifier
    if [[ "${ARN}" == arn:aws:rds:*:*:cluster:* ]]; then
      RDS_CLUSTER_IDS_FROM_TAG+=("${ARN##*:}")
      continue
    fi
  done
fi

# Merge explicit IDs
IFS=',' read -r -a EC2_IDS_EXPL <<<"${EC2_IDS_CSV:-}"
IFS=',' read -r -a RDS_INST_IDS_EXPL <<<"${RDS_INSTANCE_IDS_CSV:-}"
IFS=',' read -r -a RDS_CLUS_IDS_EXPL <<<"${RDS_CLUSTER_IDS_CSV:-}"

# De-dup helper (portable for bash 3.2)
dedup_list() {
  # Prints unique lines in the order seen
  awk '!seen[$0]++' <(printf "%s\n" "$@")
}

# Build arrays without using mapfile/readarray (not available on bash 3.2)
EC2_IDS=( $(dedup_list "${EC2_IDS_FROM_TAG[@]:-}" "${EC2_IDS_EXPL[@]:-}") )
RDS_INSTANCE_IDS=( $(dedup_list "${RDS_INSTANCE_IDS_FROM_TAG[@]:-}" "${RDS_INST_IDS_EXPL[@]:-}") )
RDS_CLUSTER_IDS=( $(dedup_list "${RDS_CLUSTER_IDS_FROM_TAG[@]:-}" "${RDS_CLUS_IDS_EXPL[@]:-}") )

if [[ ${#EC2_IDS[@]} -eq 0 && ${#RDS_INSTANCE_IDS[@]} -eq 0 && ${#RDS_CLUSTER_IDS[@]} -eq 0 ]]; then
  echo "No targets found. Provide --tag or IDs." >&2
  exit 1
fi

echo "Action: ${ACTION}"
[[ -n "${REGION}" ]] && echo "Region: ${REGION}"
[[ -n "${PROFILE}" ]] && echo "Profile: ${PROFILE}"
echo "EC2 targets: ${#EC2_IDS[@]}"
echo "RDS instance targets: ${#RDS_INSTANCE_IDS[@]}"
echo "RDS cluster targets: ${#RDS_CLUSTER_IDS[@]}"

# EC2
if [[ ${#EC2_IDS[@]} -gt 0 ]]; then
  if [[ "${ACTION}" == "stop" ]]; then
    echo "Stopping EC2 instances: ${EC2_IDS[*]}"
    awscli ec2 stop-instances --instance-ids "${EC2_IDS[@]}" >/dev/null
    if [[ "${NO_WAIT}" != "true" ]]; then
      awscli ec2 wait instance-stopped --instance-ids "${EC2_IDS[@]}"
      echo "EC2 instances stopped."
    fi
  else
    echo "Starting EC2 instances: ${EC2_IDS[*]}"
    awscli ec2 start-instances --instance-ids "${EC2_IDS[@]}" >/dev/null
    if [[ "${NO_WAIT}" != "true" ]]; then
      awscli ec2 wait instance-running --instance-ids "${EC2_IDS[@]}"
      echo "EC2 instances running."
    fi
  fi
fi

# RDS Instances
get_rds_instance_status() {
  local id="$1"
  awscli rds describe-db-instances \
    --db-instance-identifier "${id}" \
    --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "unknown"
}
poll_rds_instance_status() {
  local id="$1" want="$2"
  while true; do
    local s
    s=$(get_rds_instance_status "${id}")
    [[ "${s}" == "${want}" ]] && break
    echo "Waiting for RDS instance ${id} -> ${want} (current: ${s}) ..."
    sleep 30
  done
}
if [[ ${#RDS_INSTANCE_IDS[@]} -gt 0 ]]; then
  for id in "${RDS_INSTANCE_IDS[@]}"; do
    if [[ "${ACTION}" == "stop" ]]; then
      cur=$(get_rds_instance_status "${id}")
      case "${cur}" in
        stopped)
          echo "RDS instance ${id} already stopped."
          ;;
        stopping)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS instance ${id} is stopping; will wait only if --no-wait not set."
          else
            poll_rds_instance_status "${id}" "stopped"
          fi
          ;;
        starting)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS instance ${id} is starting; cannot stop now."
          else
            poll_rds_instance_status "${id}" "available"
            echo "Stopping RDS instance: ${id}"
            awscli rds stop-db-instance --db-instance-identifier "${id}" >/dev/null || {
              echo "Note: stop not supported for ${id} (Multi-AZ or engine type)."
              continue
            }
            poll_rds_instance_status "${id}" "stopped"
          fi
          ;;
        available|backing-up|modifying|maintenance)
          echo "Stopping RDS instance: ${id}"
          awscli rds stop-db-instance --db-instance-identifier "${id}" >/dev/null || {
            echo "Note: stop not supported for ${id} (Multi-AZ or engine type)."
            continue
          }
          [[ "${NO_WAIT}" == "true" ]] || poll_rds_instance_status "${id}" "stopped"
          ;;
        *)
          echo "RDS instance ${id} in unsupported state '${cur}'. Skipping."
          ;;
      esac
    else
      cur=$(get_rds_instance_status "${id}")
      case "${cur}" in
        available)
          echo "RDS instance ${id} already available."
          ;;
        starting)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS instance ${id} is already starting."
          else
            poll_rds_instance_status "${id}" "available"
          fi
          ;;
        stopped)
          echo "Starting RDS instance: ${id}"
          awscli rds start-db-instance --db-instance-identifier "${id}" >/dev/null || {
            echo "Failed to start ${id}."
            continue
          }
          [[ "${NO_WAIT}" == "true" ]] || poll_rds_instance_status "${id}" "available"
          ;;
        stopping)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS instance ${id} is stopping; cannot start yet."
          else
            poll_rds_instance_status "${id}" "stopped"
            echo "Starting RDS instance: ${id}"
            awscli rds start-db-instance --db-instance-identifier "${id}" >/dev/null || {
              echo "Failed to start ${id}."
              continue
            }
            poll_rds_instance_status "${id}" "available"
          fi
          ;;
        *)
          echo "RDS instance ${id} in state '${cur}'. Not starting."
          ;;
      esac
    fi
  done
fi

# RDS Clusters (Aurora)
get_rds_cluster_status() {
  local id="$1"
  awscli rds describe-db-clusters \
    --db-cluster-identifier "${id}" \
    --query 'DBClusters[0].Status' --output text 2>/dev/null || echo "unknown"
}
poll_rds_cluster_status() {
  local id="$1" want="$2"
  while true; do
    local s
    s=$(get_rds_cluster_status "${id}")
    [[ "${s}" == "${want}" ]] && break
    echo "Waiting for RDS cluster ${id} -> ${want} (current: ${s}) ..."
    sleep 30
  done
}
if [[ ${#RDS_CLUSTER_IDS[@]} -gt 0 ]]; then
  for id in "${RDS_CLUSTER_IDS[@]}"; do
    if [[ "${ACTION}" == "stop" ]]; then
      cur=$(get_rds_cluster_status "${id}")
      case "${cur}" in
        stopped)
          echo "RDS cluster ${id} already stopped."
          ;;
        stopping)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS cluster ${id} is stopping; will wait only if --no-wait not set."
          else
            poll_rds_cluster_status "${id}" "stopped"
          fi
          ;;
        starting)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS cluster ${id} is starting; cannot stop now."
          else
            poll_rds_cluster_status "${id}" "available"
            echo "Stopping RDS cluster: ${id}"
            awscli rds stop-db-cluster --db-cluster-identifier "${id}" >/dev/null || {
              echo "Note: stop not supported for cluster ${id}."
              continue
            }
            poll_rds_cluster_status "${id}" "stopped"
          fi
          ;;
        available|backing-up|modifying|maintenance)
          echo "Stopping RDS cluster: ${id}"
          awscli rds stop-db-cluster --db-cluster-identifier "${id}" >/dev/null || {
            echo "Note: stop not supported for cluster ${id}."
            continue
          }
          [[ "${NO_WAIT}" == "true" ]] || poll_rds_cluster_status "${id}" "stopped"
          ;;
        *)
          echo "RDS cluster ${id} in unsupported state '${cur}'. Skipping."
          ;;
      esac
    else
      cur=$(get_rds_cluster_status "${id}")
      case "${cur}" in
        available)
          echo "RDS cluster ${id} already available."
          ;;
        starting)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS cluster ${id} is already starting."
          else
            poll_rds_cluster_status "${id}" "available"
          fi
          ;;
        stopped)
          echo "Starting RDS cluster: ${id}"
          awscli rds start-db-cluster --db-cluster-identifier "${id}" >/dev/null || {
            echo "Failed to start cluster ${id}."
            continue
          }
          [[ "${NO_WAIT}" == "true" ]] || poll_rds_cluster_status "${id}" "available"
          ;;
        stopping)
          if [[ "${NO_WAIT}" == "true" ]]; then
            echo "RDS cluster ${id} is stopping; cannot start yet."
          else
            poll_rds_cluster_status "${id}" "stopped"
            echo "Starting RDS cluster: ${id}"
            awscli rds start-db-cluster --db-cluster-identifier "${id}" >/dev/null || {
              echo "Failed to start cluster ${id}."
              continue
            }
            poll_rds_cluster_status "${id}" "available"
          fi
          ;;
        *)
          echo "RDS cluster ${id} in state '${cur}'. Not starting."
          ;;
      esac
    fi
  done
fi

echo "Done."