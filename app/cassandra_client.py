import os
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy

CASSANDRA_HOST     = os.getenv("CASSANDRA_HOST", "127.0.0.1")
CASSANDRA_PORT     = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "estoque")

_cluster = None
_session = None


def get_session():
    global _cluster, _session
    if _session is None:
        _cluster = Cluster(
            contact_points=[CASSANDRA_HOST],
            port=CASSANDRA_PORT,
            load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
            protocol_version=5,
        )
        _session = _cluster.connect(CASSANDRA_KEYSPACE)
        _session.default_timeout = 30
    return _session


def close():
    global _cluster, _session
    if _cluster:
        _cluster.shutdown()
    _cluster = None
    _session = None
