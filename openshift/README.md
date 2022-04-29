Deploy Copr build system in OpenShift
=====================================

... in two minutes, if you have a configuration file in hand.

This directory contains the deployment scripts and base configuration that
allows you to quickly deploy a fully-working Copr build system infrastructure
into an OpenShift cluster, with builders (virtual machines) being automatically
started/stopped in external clouds (currently just pre-configured AWS).

Note: At the time of writing this document, it is not common to be able to start
privileged containers in OpenShift, nor rootless containers (user namespaces).
Therefore, builders need to stay as virtual machines only.

1. get an OpenShift Cluster
2. get AWS token (for EC2 access)
3. $ cp secret-vars.yml.template secret-vars.yml and fill the gaps
4. hit the $ make

Currently we maintain the images here: https://quay.io/organization/copr

WARNING: This deployment is in a pre-production state!

TODO list
---------

- copr-keygen pod signing process needs to be secured, currently the pod accepts
  sign requests from any other pod in the project because we "allow 0.0.0.0/0"

- start logging to stdout/stderr, so we can just do
  'oc logs <podname> -c <container>', according to
  https://docs.openshift.com/container-platform/4.9/openshift_images/create-images.html
  Alternatively at least implement log-rotation.

- we should merge https://github.com/openSUSE/obs-sign/pull/36 - currently
  patched Fedora-only

- zombie reaping - use tini

- Let's Encrypt automation

- starting the containers against a locally maintained code (from git root),
  currently we just use 'docker-compose'

- automate PostgreSQL initialization from a SQL dump file, for easier debugging
  of complicated scenarios

- setup cron jobs (automatic build removals, etc.)

- better container image tagging (currently everything in :test)

- automatic image builds (quay.io builds are broken for F35
  https://bugzilla.redhat.com/show_bug.cgi?id=2025899)

- automatize the AWS SSH key creation/removal (this is the hardest part in the
  secret-vars.yml config file)

- separate the normal and secret vars (now everything is in secret-vars.yml)


Research
========

- write an operator for starting builders hosted in OpenShift?  But we need to
  wait for the state when "user namespaces" are "commonly" available

- automatic termination of orphaned resalloc instances - this happens easily
  when project is deleted (oc delete project <your project>)

- experiment with Terraform
