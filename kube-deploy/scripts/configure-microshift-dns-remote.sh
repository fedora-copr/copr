#!/bin/bash
# Runs *inside* the CRC MicroShift VM (invoked over SSH by the
# `configure-microshift-dns` just recipe, as `sudo bash -s -- <router_ip>
# <route_hosts_base64>`).
#
# Diffs the desired /etc/microshift/hosts + dns.hosts config against what's
# already on disk, and only writes + restarts MicroShift if something
# changed (a restart costs ~10-60s of API downtime).
#
# Exit codes: 0 = nothing to do, 10 = wrote config and restarted MicroShift
# (caller should wait for the API to come back), anything else = error.
#
# This is hack to make distgit-importer (running in a builder pod) able to
# reach copr-backend-copr.apps.crc.testing as well as users can
# comfortably navigate berween URLs of different instances.
set -euo pipefail

ROUTER_IP="$1"
ROUTE_HOSTS=$(echo "$2" | base64 -d)

DESIRED_HOSTS_FILE=$(printf '%s\n' "$ROUTE_HOSTS" | while read -r host; do
    [ -n "$host" ] && printf '%s %s\n' "$ROUTER_IP" "$host"
done)
DESIRED_MS_CONFIG=$'dns:\n  hosts:\n    status: Enabled\n    file: /etc/microshift/hosts\n'

CURRENT_HOSTS_FILE=$(cat /etc/microshift/hosts 2>/dev/null || true)
CURRENT_MS_CONFIG=$(cat /etc/microshift/config.yaml 2>/dev/null || true)

if [ "$DESIRED_HOSTS_FILE" = "$CURRENT_HOSTS_FILE" ] && [ "$DESIRED_MS_CONFIG" = "$CURRENT_MS_CONFIG" ]; then
    echo "  CoreDNS route hosts already configured"
    exit 0
fi

printf '%s\n' "$DESIRED_HOSTS_FILE" > /etc/microshift/hosts
printf '%s' "$DESIRED_MS_CONFIG" > /etc/microshift/config.yaml
echo "  Route hostnames written to /etc/microshift/hosts -> $ROUTER_IP; restarting MicroShift..."
systemctl restart microshift
exit 10
