#!/bin/bash

/usr/bin/supervisord -c /etc/supervisord.conf

cat <<-EOF
  echo "#########################################################"
  echo "###   Your development instance of Copr Dist Git      ###"
  echo "###   is now running at: http://localhost:5001/cgit   ###"
  echo "#########################################################"
EOF

/bin/bash
