from fabazon.ec2 import EC2TagManager


class EC2RoleDefs(dict):
    """Represents a dictionary of Fabric roledefs for EC2 instances.

    This can be used instead of hard-coding a list of hostnames in a Fabric
    file. When accessing the list of hosts for a role, it will query AWS
    for all EC2 instances with the provided role and other required tags.

    By default, this will look up with 'role=<name>', but the 'role'
    attribute can be changed by passing a custom role_tag.
    """
    def __init__(self, regions, roles=[], role_tag='role', require_tags={}):
        super(EC2RoleDefs, self).__init__()

        self.tag_manager = EC2TagManager(regions)

        self.role_tag = role_tag
        self.require_tags = require_tags
        self.roles = roles

        for role in roles:
            self[role] = None

    def __getitem__(self, role):
        result = super(EC2RoleDefs, self).__getitem__(role)

        if result is None:
            tags = {
                self.role_tag: role,
            }
            tags.update(self.require_tags)

            result = self.tag_manager.get_tagged_hostnames(**tags)
            self[role] = result

        return result
