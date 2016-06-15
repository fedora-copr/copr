#!/bin/bash

export LANG=en_US.UTF-8

echo '127.0.0.1 keygen' > /etc/hosts
echo 4096 > /proc/sys/net/core/somaxconn
/usr/bin/supervisord -c /etc/supervisord.conf
/bin/bash
