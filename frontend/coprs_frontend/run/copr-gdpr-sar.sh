#!/usr/bin/bash
# Purpose of this script is to be remotely executed from batcave01
# to collect user SAR data
# Read more: http://fedora-infra-docs.readthedocs.io/en/latest/sysadmin-guide/sops/gdpr_sar.html
# Playbook: https://infrastructure.fedoraproject.org/cgit/ansible.git/tree/playbooks/manual/gdpr/sar.yml
# Usage: SAR_USERNAME=someusername copr-gdpr-sar.sh
copr-frontend dump-user $SAR_USERNAME
