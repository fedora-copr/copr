Statistics
==========

Logstash [1] is used to parse web server logs, filter interesting events (i.e. rpm file downloads) and send json
to frontend. Logstash config doesn't have a nice option to define variables, so config should be copied manually after
the installation and frontend host should be fixed there.

--
1. - http://logstash.net/
