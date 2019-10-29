#!/bin/bash

/usr/bin/supervisord -c /etc/supervisord.conf

cat <<-EOF
  echo "#########################################################"
  echo "###   Your development instance of Copr Dist Git      ###"
  echo "###   is now running at: http://localhost:5001/cgit   ###"
  echo "#########################################################"
EOF

# We have a recurring problem with httpd, which manifests itself
# in the following way
# 1. httpd is running, while supervisorctl thinks it failed
# 2. It is not accessible e.g. via curl and returns "connection refused"
# 3. Killing httpd and starting it again fixes the issue
kill -9 `pidof httpd` && supervisorctl start httpd

/bin/bash
