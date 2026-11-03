FROM quay.io/frrouting/frr:containerlab-10.7.1

USER root

RUN apk add --no-cache net-snmp net-snmp-tools

COPY lab/images/frr-snmp/snmpd.conf /etc/snmp/snmpd.conf