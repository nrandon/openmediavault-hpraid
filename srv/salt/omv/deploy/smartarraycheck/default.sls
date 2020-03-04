# @license   http://www.gnu.org/licenses/gpl.html GPL Version 3
# @author    OpenMediaVault Plugin Developers <plugins@omv-extras.org>
# @copyright Copyright (c) 2022 OpenMediaVault Plugin Developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

{% set email_config = salt['omv_conf.get']('conf.system.notification.email') %}
{% set config = salt['omv_conf.get']('conf.service.smartarraycheck') %}

{% if (config.enable | to_bool) and (email_config.enable | to_bool) %}

configure_smartarraycheck:
  file.managed:
    - name: "/etc/smartarraycheck.d/config.yml"
    - source:
      - salt://{{ tpldir }}/files/etc_smartarraycheck.d_config_yml.j2
    - makedirs: true
    - template: jinja
    - context:
        config: {{ config.controllers | yaml }}
    - user: root
    - group: root
    - mode: 644

service_smartarraycheck:
  file.managed:
    - name: "/etc/systemd/system/smartarraycheck.service"
    - source:
      - salt://{{ tpldir }}/files/etc_systemd_system_smartarraycheck_service.j2
    - template: jinja
    - context:
        email_config: {{ email_config | json }}
        config: {{ config | json }}
    - user: root
    - group: root
    - mode: 644

start_smartarraycheck_service:
  service.running:
    - name: smartarraycheck
    - enable: True
    - watch:
      - file: configure_smartarraycheck
      - file: service_smartarraycheck

{% else %}

config_smartarraycheck_disabled:
  cmd.run:
    - name: >
        . /usr/share/openmediavault/scripts/helper-functions &&
        omv_config_update "/config/services/smartarraycheck/enable" "0"

stop_smartarraycheck_service:
  service.dead:
    - name: smartarraycheck
    - enable: False

{% endif %}
