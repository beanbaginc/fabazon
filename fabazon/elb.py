import time

from boto.ec2.elb import ELBConnection
from fabric.colors import red


class LoadBalancer(object):
    def __init__(self, name):
        self.name = name
        self._cnx = ELBConnection()

    def register_instance(self, instance):
        self._cnx.register_instances(self.name, [instance.id])

    def unregister_instance(self, instance):
        self._cnx.deregister_instances(self.name, [instance.id])

    def is_instance_healthy(self, instance):
        health_info = self._cnx.describe_instance_health(self.name,
                                                         [instance.id])
        assert len(health_info) == 1
        assert health_info[0].instance_id == instance.id

        return health_info[0].state == 'InService'

    def wait_until_instance_healthy(self, instance):
        # Wait for the instance to become healthy. We'll wait up to
        # 60 seconds (+ request times).
        for i in xrange(60):
            healthy = self.is_instance_healthy(instance)

            if healthy:
                return True

            time.sleep(1)

        print red('Instance %s was not healthy after 60 seconds')
        return False
