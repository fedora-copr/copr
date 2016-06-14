#!/bin/bash

export LANG=en_US.UTF-8

/usr/bin/supervisord -c /etc/supervisord.conf
echo 4096 > /proc/sys/net/core/somaxconn
/bin/bash
