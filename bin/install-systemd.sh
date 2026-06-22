#!/usr/bin/env bash

set -euo pipefail


SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"


ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/lib/load-config.rc"
SERVICE_NAME="btrfs-churn-mon"

usage() {

cat <<USAGE

Usage:

  install-systemd.sh --install
  install-systemd.sh --dry-run
  install-systemd.sh --stdout
  install-systemd.sh --help

Options:

  --install
      Install and enable systemd units

  --dry-run
      Show actions without modifying system

  --stdout
      Show files and actions

  --help
      Show this help

USAGE

}

show_plan() {

cat <<PLAN

Service file:

  ${SYSTEMD_DIR}/${SERVICE_NAME}.service

Timer file:

  ${SYSTEMD_DIR}/${SERVICE_NAME}.timer

Source files:

  ${ROOT}/systemd/${SERVICE_NAME}.service
  ${ROOT}/systemd/${SERVICE_NAME}.timer

Commands:

  systemctl daemon-reload

  systemctl enable ${SERVICE_NAME}.timer

  systemctl start ${SERVICE_NAME}.timer

PLAN

}

MODE=""

while [[ $# -gt 0 ]]
do
    case "$1" in

        --install)
            MODE="install"
            shift
            ;;

        --dry-run)
            MODE="dry-run"
            shift
            ;;

        --stdout)
            MODE="stdout"
            shift
            ;;

        --help|-h)
            usage
            exit 0
            ;;

        *)
            echo "ERROR: unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

MODE="${MODE:-stdout}"

case "$MODE" in

    stdout)

        show_plan
        exit 0
        ;;

    dry-run)

        echo
        echo "DRY RUN"
        echo

        show_plan

        exit 0
        ;;

    install)

        mkdir -p "$PREFIX"

        install -m 644 \
            "${ROOT}/systemd/${SERVICE_NAME}.service" \
            "${SYSTEMD_DIR}/"

        install -m 644 \
            "${ROOT}/systemd/${SERVICE_NAME}.timer" \
            "${SYSTEMD_DIR}/"

        systemctl daemon-reload

        systemctl enable \
            "${SERVICE_NAME}.timer"

        systemctl start \
            "${SERVICE_NAME}.timer"

        echo
        echo "Installed."
        echo

        systemctl status \
            "${SERVICE_NAME}.timer" \
            --no-pager \
            || true

        ;;

esac

