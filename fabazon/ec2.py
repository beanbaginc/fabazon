"""EC2 connection management."""

from __future__ import annotations

import os
from typing import Any, Optional, Sequence

import boto3

from fabric.api import run
from fabric.colors import red
from typing_extensions import Self


def get_current_instance_id() -> Optional[str]:
    """Return the ID of the current EC2 host.

    This will run a command on the currently-connected host and return the
    resulting instance.

    Returns:
        str:
        The EC2 instance ID, or ``None`` if it could not be determined.
    """
    s = run('ec2-metadata -i', quiet=True).strip()

    if not s.startswith('instance-id'):
        print(red('Failed to get instance ID. Got: "%s"' % s))
        return None

    return s.split(' ')[1]


class EC2Instance:
    """A wrapper around an EC2 instance."""

    ######################
    # Instance variables #
    ######################

    #: The ID of the EC2 instance.
    id: str

    @classmethod
    def for_current_host(cls) -> Optional[Self]:
        """Return an instance for the current Fabric host.

        Returns:
            EC2Instance:
            The instance matching the host, or ``None`` if not found.
        """
        instance_id = get_current_instance_id()

        if not instance_id:
            return None

        return cls(instance_id=instance_id)

    def __init__(
        self,
        *,
        instance_id: str,
    ) -> None:
        """Initialize the instance.

        Version Changed:
            2.0:
            ``instance_id`` is now a keyword-only argument.

        Args:
            instance_id (str):
                The ID of the instance.
        """
        self.id = instance_id


class EC2TagManager:
    """Provides functionality for working with tags on EC2 instances."""

    ######################
    # Instance variables #
    ######################

    #: The regions to scan.
    regions: Sequence[str]

    #: A mapping of regions to Boto EC2 client connections.
    region_cnx: dict[str, Any]

    def __init__(
        self,
        *,
        regions: Sequence[str],
    ) -> None:
        """Initialize the tag manager.

        Version Changed:
            2.0:
            Made ``regions`` a keyword-only argment.

        Args:
            regions (list of str):
                The list of regions to scan.
        """
        self.regions = regions
        self.region_cnx = {}

        session = boto3.Session(
            profile_name=os.environ.get('FABAZON_AWS_PROFILE'))

        for region in regions:
            self.region_cnx[region] = session.client('ec2', region_name=region)

    def get_tagged_hostnames(
        self,
        *,
        running_only: bool = True,
        tags: dict[str, str],
    ) -> Sequence[str]:
        """Returns the hostnames of all instances with the given tags.

        This can be used to dynamically build Fabric host lists based on
        configured EC2 instances.

        Version Changed:
            2.0:
            * Made ``running_only`` a keyword-only argument.
            * Made ``tags`` a keyword-only dictionary argument instead of
              passing as individual keyword arguments.

        Args:
            running_only (bool, optional):
                Whether to return only running instances.

            tags (dict, optional):
                Any tags to filter by.

        Returns:
            list of str:
            The list of hostnames matching the criteria.
        """
        hostnames: list[str] = []
        tag_filter: list[dict[str, Any]] = [
            {
                'Name': f'tag:{key}',
                'Values': [value],
            }
            for key, value in tags.items()
        ]

        for cnx in self.region_cnx.values():
            response = cnx.describe_instances(Filters=tag_filter)

            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if (not running_only or
                        instance['State']['Name'] == 'running'):
                        dns_name = instance.get('PublicDnsName')

                        if dns_name:
                            hostnames.append(dns_name)

        return hostnames
