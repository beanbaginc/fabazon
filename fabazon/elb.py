"""AWS load balancer utilities."""

from __future__ import annotations

import os
import time
from typing import Mapping, TYPE_CHECKING

import boto3
from fabric.colors import red

if TYPE_CHECKING:
    from fabazon.ec2 import EC2Instance


class BaseLoadBalancer:
    """Base class for a load balancer.

    This provides some base functions for the different load balancers.
    It's otherwise a very thin base class.
    """

    def wait_until_instance_healthy(
        self,
        instance: EC2Instance,
    ) -> bool:
        """Waits until the given instance is healthy before returning.

        This will wait up to 60 seconds for the instance to be marked as
        healthy by the load balancer, displaying an error if it times out.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to wait for.

        Returns:
            bool:
            ``True`` if the instance became healthy.
            ``False`` if it timed out waiting.
        """
        # Wait for the instance to become healthy. We'll wait up to
        # 60 seconds (+ request times).
        for i in range(60):
            if self.is_instance_healthy(instance):
                return True

            time.sleep(1)

        print(red('Instance %s was not healthy after 60 seconds'))
        return False

    def wait_until_instance_removed(
        self,
        instance: EC2Instance,
    ) -> bool:
        """Waits until the given instance is removed before returning.

        This will wait up to 60 seconds for the instance to no longer be
        registered on the load balancer, displaying an error if it times out.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to wait for.

        Returns:
            bool:
            ``True`` if the instance was confirmed removed.
            ``False`` if it timed out waiting.
        """
        for i in range(60):
            if not self.is_instance_registered(instance):
                return True

            time.sleep(1)

        print(red('Instance %s was still registered after 60 seconds'))
        return False

    def register_instance(
        self,
        instance: EC2Instance,
    ) -> None:
        """Register an instance on the load balancer.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to register.
        """
        raise NotImplementedError

    def unregister_instance(
        self,
        instance: EC2Instance,
    ) -> None:
        """Unregister an instance from the load balancer.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to unregister.
        """
        raise NotImplementedError

    def is_instance_registered(
        self,
        instance: EC2Instance,
    ) -> bool:
        """Return whether an instance is registered.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to check.

        Returns:
            bool:
            ``True`` if the instance is registered on the load balancer.
            ``False`` if it's not registered.
        """
        raise NotImplementedError

    def is_instance_healthy(
        self,
        instance: EC2Instance,
    ) -> bool:
        """Return whether an instance is healthy.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to check.

        Returns:
            bool:
            ``True`` if the instance is healthy.
            ``False`` if it's not healthy.
        """
        raise NotImplementedError


class LoadBalancerV2(BaseLoadBalancer):
    """A modern AWS load balancer supporting ALB and NLB.

    This is used to interface with the Application/Network Load Balancers,
    which support VPC and more advanced routing.

    If using the classic Elastic Load Balancer, use :py:class:`LoadBalancer`.
    """

    def __init__(
        self,
        *,
        target_group_arn: str,
        region: str,
    ) -> None:
        """Initialize the instance.

        Version Changed:
            2.0:
            ``target_group_arn`` and ``region`` are now keyword-only
            arguments.

        Args:
            target_group_arn (str):
                The ARN of the target group on the load balancer.

            region (str):
                The region the load balancer is in.
        """
        self.target_group_arn = target_group_arn

        session = boto3.Session(
            profile_name=os.environ.get('FABAZON_AWS_PROFILE'))
        self._cnx = session.client('elbv2', region_name=region)

    def register_instance(
        self,
        instance: EC2Instance,
    ) -> None:
        """Register an instance on the load balancer.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to register.
        """
        self._cnx.register_targets(
            TargetGroupArn=self.target_group_arn,
            Targets=[{
                'Id': instance.id,
            }])

    def unregister_instance(
        self,
        instance: EC2Instance,
    ) -> None:
        """Unregister an instance from the load balancer.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to unregister.
        """
        self._cnx.deregister_targets(
            TargetGroupArn=self.target_group_arn,
            Targets=[{
                'Id': instance.id,
            }])

    def is_instance_registered(
        self,
        instance: EC2Instance,
    ) -> bool:
        """Return whether an instance is registered.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to check.

        Returns:
            bool:
            ``True`` if the instance is registered on the load balancer.
            ``False`` if it's not registered.
        """
        health_info = self._get_instance_health_info(instance)

        return health_info.get('Reason') != 'Target.NotRegistered'

    def is_instance_healthy(
        self,
        instance: EC2Instance,
    ) -> bool:
        """Return whether an instance is healthy.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to check.

        Returns:
            bool:
            ``True`` if the instance is healthy.
            ``False`` if it's not healthy.
        """
        health_info = self._get_instance_health_info(instance)

        return health_info['State'] == 'healthy'

    def _get_instance_health_info(
        self,
        instance: EC2Instance,
    ) -> Mapping[str, str]:
        """Return health information for an instance.

        Args:
            instance (fabazon.ec2.EC2Instance):
                The instance to check.

        Returns:
            dict:
            Information on the instance's health.
        """
        rsp = self._cnx.describe_target_health(
            TargetGroupArn=self.target_group_arn,
            Targets=[{
                'Id': instance.id,
            }])

        health_info = rsp['TargetHealthDescriptions']
        assert len(health_info) == 1
        assert health_info[0]['Target']['Id'] == instance.id

        return health_info[0]['TargetHealth']
