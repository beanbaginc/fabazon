"""EC2 role definition scanning."""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from fabazon.ec2 import EC2TagManager


class EC2RoleDefs(dict[str, Optional[Sequence[str]]]):
    """Represents a dictionary of Fabric roledefs for EC2 instances.

    This can be used instead of hard-coding a list of hostnames in a Fabric
    file. When accessing the list of hosts for a role, it will query AWS
    for all EC2 instances with the provided role and other required tags.

    By default, this will look up with 'role=<name>', but the 'role'
    attribute can be changed by passing a custom role_tag.
    """

    ######################
    # Instance variables #
    ######################

    #: The tags to require for any matches.
    require_tags: Mapping[str, str]

    #: The tag name used to identify a role.
    role_tag: str

    #: The list of roles to scan.
    roles: Sequence[str]

    #: The associated EC2 tag manager.
    tag_manager: EC2TagManager

    #: Whether to use SSM support.
    use_ssm: bool

    def __init__(
        self,
        *,
        regions: Sequence[str],
        roles: Sequence[str] = [],
        role_tag: str = 'role',
        require_tags: Mapping[str, str] = {},
        use_ssm: bool = False,
    ) -> None:
        """Initialize the role definitions.

        This will pre-populate the dictionary, mapping all roles to ``None``.

        Version Changed:
            * Made all arguments keyword-only arguments.
            * Added SSM support via the ``use_ssm`` argument.

        Args:
            regions (list of str):
                The list of regions to scan.

            roles (list of str, optional):
                The list of roles to scan.

            role_tag (str, optional):
                The tag used to identify a role.

            require_tags (dict, optional):
                The tags required for any matches.

            use_ssm (bool, optional):
                Whether to use SSM support.

                If set, this dictionary will map to EC2 identifiers rather
                than hostnames.

                Version Added:
                    2.0
        """
        super().__init__()

        self.tag_manager = EC2TagManager(regions=regions)

        self.role_tag = role_tag
        self.require_tags = require_tags
        self.roles = roles
        self.use_ssm = use_ssm

        for role in roles:
            self[role] = None

    def __getitem__(
        self,
        role: str,
    ) -> Optional[Sequence[str]]:
        """Return a list of hostnames matching the role.

        Args:
            role (str):
                The name of the role.

        Returns:
            list of str:
            The list of hostnames matching the role, or ``None`` if not found.
        """
        result = super().__getitem__(role)

        if result is None:
            tags: dict[str, str] = {
                self.role_tag: role,
            }
            tags.update(self.require_tags)

            if self.use_ssm:
                result = self.tag_manager.get_tagged_instance_ids(tags=tags)
            else:
                result = self.tag_manager.get_tagged_hostnames(tags=tags)

            self[role] = result

        return result
