# coding: utf-8

from jinja2 import Environment

template_string = """\
# This is development/testing only mock profile, not exactly the same as
# is used on copr builders;  but it is basically similar.  If you need an
# exact mock configuration (because you e.g. try to reproduce failed
# build), such configuration is put alongside the built RPMs.

include('/etc/mock/{{chroot}}.cfg')

config_opts['root'] = '{{project_id}}_{{chroot}}'
config_opts['chroot_additional_packages'] = '
{%- for pkg in additional_packages -%}
{%- if loop.last -%}
{{ pkg }}
{%- else -%}
{{ pkg }} {% endif -%}
{%- endfor -%}'

{% if repos %}
config_opts['yum.conf'] += \"\"\"
{% for repo in repos %}
[{{ repo.id }}]
name="{{ repo.name }}"
baseurl={{ repo.url }}
gpgcheck=0
enabled=1
skip_if_unavailable=1
metadata_expire=0
cost=1
best=1
{% endfor %}
\"\"\"
{% endif %}
"""

class MockProfile(object):
    def __init__(self, data):
        self.data = data

    def __str__(self):
        template = Environment().from_string(template_string)
        return template.render(self.data)



