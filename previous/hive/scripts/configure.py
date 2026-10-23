#!/usr/bin/env python3
"""Generate private metastore config once; keep the password across redeploys."""
import os
from pathlib import Path
import secrets
from xml.etree.ElementTree import Element, SubElement, ElementTree

root = Path(__file__).resolve().parents[1]
env = root / '.env'
if not env.exists():
    env.write_text('METASTORE_PASSWORD=' + secrets.token_hex(24) + '\n')
    env.chmod(0o600)
password = dict(line.split('=', 1) for line in env.read_text().splitlines() if '=' in line)['METASTORE_PASSWORD']
props = {
    'javax.jdo.option.ConnectionURL': 'jdbc:postgresql://127.0.0.1:5432/metastore',
    'javax.jdo.option.ConnectionDriverName': 'org.postgresql.Driver',
    'javax.jdo.option.ConnectionUserName': 'hive',
    'javax.jdo.option.ConnectionPassword': password,
    'hive.metastore.uris': 'thrift://127.0.0.1:9083',
    'metastore.thrift.bind.host': '127.0.0.1',
    'hive.metastore.warehouse.dir': '/user/hive/warehouse',
    'hive.metastore.warehouse.external.dir': '/user/hive/warehouse-external',
    'hive.metastore.schema.verification': 'true',
    'datanucleus.schema.autoCreateAll': 'false',
    'hive.server2.thrift.bind.host': '10.27.0.12',
    'hive.server2.thrift.port': '10000',
    'hive.server2.webui.host': '127.0.0.1',
    'hive.server2.webui.port': '10002',
    'hive.server2.enable.doAs': 'false',
    'hive.server2.authentication': 'NONE',
    'hive.server2.thrift.min.worker.threads': '5',
    'hive.server2.thrift.max.worker.threads': '50',
    'hive.execution.engine': 'mr',
    'hive.exec.mode.local.auto': 'false',
    'hive.exec.scratchdir': '/tmp/hive',
    'hive.exec.reducers.max': '1',
    'hive.stats.autogather': 'false',
    'hive.cbo.enable': 'false',
    'hive.fetch.task.conversion': 'more',
    'hive.query.results.cache.enabled': 'false',
    'hive.server2.logging.operation.enabled': 'true',
}
config = Element('configuration')
for name, value in props.items():
    prop = SubElement(config, 'property')
    SubElement(prop, 'name').text = name
    SubElement(prop, 'value').text = value
target = root / 'config/hive-site.xml'
ElementTree(config).write(target, encoding='utf-8', xml_declaration=True)
target.chmod(0o644)  # readable by the hive container user; contains local-only DB password
print('Generated config/hive-site.xml; credentials are ignored by git')
