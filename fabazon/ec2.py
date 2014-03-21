from boto import ec2

from fabric.api import run
from fabric.colors import red


def get_current_instance_id():
    s = run('ec2-metadata -i', quiet=True).strip()

    if not s.startswith('instance-id'):
        print red('Failed to get instance ID. Got: "%s"' % s)
        return None

    return s.split(' ')[1]


class EC2Instance(object):
    @classmethod
    def for_current_host(cls):
        instance_id = get_current_instance_id()

        if not instance_id:
            return None

        return cls(instance_id)

    def __init__(self, instance_id):
        self.id = instance_id


class EC2TagManager(object):
    """Provides functionality for working with tags on EC2 instances."""
    def __init__(self, regions):
        self.regions = regions
        self.region_cnx = {}

        for region in regions:
            self.region_cnx[region] = ec2.connect_to_region(region)

    def get_tagged_hostnames(self, running_only=True, **tags):
        """Returns the hostnames of all instances with the given tags.

        This can be used to dynamically build Fabric host lists based on
        configured EC2 instances.
        """
        hostnames = []
        tag_filter = {}

        for key, value in tags.iteritems():
            tag_filter['tag:' + key] = value

        for cnx in self.region_cnx.itervalues():
            instances = cnx.get_only_instances(filters=tag_filter)

            for instance in instances:
                if running_only and instance.state != 'running':
                    continue

                hostnames.append(instance.public_dns_name)

        return hostnames
