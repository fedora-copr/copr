.. _monitoring:

How Fedora Copr is monitored
============================

`Nagios`_ (with `hypervisors' checks`_) and `Nagios external`_ are the main monitoring services for Fedora
Copr.  That's by fact that the `Fedora Infrastructure`_ team uses Nagios, and we
tightly cooperate with that team (they help us with the ping&power support).

But we also — as a secondary solution — use the `Prometheus`_ monitoring
(Graphana UI, visible internally within Red Hat).

We do the normal availability checks, storage space consumption checks, etc. but
we also have the functionality "black-box" `copr-ping test`_ that
`periodically submits`_ a simple build testing the whole Copr stack.  This test is
triggered from the ``copr-backend`` server.

On weekly basis, we `analyze storage`_ consumption to gather `usage statistics`_.

On top of that all, we also use `UptimeRobot`_ to geographically check that our
CDN (implemented with `AWS CloudFront`_) for ``copr-backend`` works everywhere.

The following image illustrates the monitoring work-flow:

.. image:: /_static/monitoring-schema.uml.png

.. _`Fedora Infrastructure`: https://pagure.io/fedora-infrastructure
.. _`AWS CloudFront`: https://aws.amazon.com/cloudfront/
.. _`UptimeRobot`: https://uptimerobot.com/
.. _`Prometheus`: https://prometheus.io/
.. _`Nagios`: https://nagios.fedoraproject.org/nagios/cgi-bin//status.cgi?hostgroup=copr_all_instances_aws&style=overview
.. _`Nagios external`: https://nagios-external.fedoraproject.org/nagios/cgi-bin//status.cgi?hostgroup=copr_all_instances_aws&style=overview
.. _`copr-ping test`: https://pagure.io/fedora-infra/ansible/blob/main/f/roles/copr/backend/tasks/copr-ping.yml
.. _`periodically submits`: https://copr.fedorainfracloud.org/coprs/g/copr/copr-ping/builds/
.. _`usage statistics`: https://copr-be.cloud.fedoraproject.org/stats/index.html
.. _`analyze storage`: https://github.com/fedora-copr/copr/blob/main/backend/run/copr-backend-analyze-results
.. _`hypervisors' checks`: https://nagios.fedoraproject.org/nagios/cgi-bin//status.cgi?hostgroup=copr_hypervisor&style=detail
