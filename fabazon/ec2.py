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
