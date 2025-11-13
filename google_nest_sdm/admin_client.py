"""Admin Client library for the Google Nest SDM API.

This manages administrative tasks for setting up pubsub topics and subscriptions.

This library exists to provide an asyncio interface given that the current pubsub
clients are synchronous.
"""

import logging
import re
import asyncio
from typing import Any
from dataclasses import dataclass, field

from .diagnostics import SUBSCRIBER_DIAGNOSTICS as DIAGNOSTICS
from .auth import AbstractAuth
from .exceptions import (
    ApiException,
    NotFoundException,
    ApiForbiddenException,
    ConfigurationException,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "AdminClient",
    "EligibleTopics",
    "EligibleSubscriptions",
    "validate_subscription_name",
    "validate_topic_name",
    "PUBSUB_API_HOST",
]

PUBSUB_API_HOST = "https://pubsub.googleapis.com/v1"
SDM_MANAGED_TOPIC_FORMAT = (
    "projects/sdm-prod/topics/enterprise-{device_access_project_id}"
)

# Used to catch invalid subscriber id
EXPECTED_SUBSCRIBER_REGEXP = re.compile("^projects/[^/]+/subscriptions/[^/]+$")

# Used to catch a topic misconfiguration
EXPECTED_TOPIC_REGEXP = re.compile("^projects/[^/]+/topics/[^/]+$")

# Topic prefix for the project
EXPECTED_PROJECS_PREFIX = re.compile("^projects/[^/]+$")


@dataclass
class EligibleTopics:
    """Eligible topics for the project."""

    topic_names: list[str] = field(default_factory=list)


@dataclass
class EligibleSubscriptions:
    """Eligible topics for the project."""

    subscription_names: list[str] = field(default_factory=list)


# Policy that gives Device Access Console permission to publish to a topic
DEFAULT_TOPIC_IAM_POLICY = {
    "bindings": [
        {
            "members": ["group:sdm-publisher@googlegroups.com"],
            "role": "roles/pubsub.publisher",
        }
    ]
}


def validate_subscription_name(subscription_name: str) -> None:
    """Validates that a subscription name is correct.

    Raises ConfigurationException on failure.
    """
    if not EXPECTED_SUBSCRIBER_REGEXP.match(subscription_name):
        DIAGNOSTICS.increment("subscription_name_invalid")
        _LOGGER.debug("Subscription name did not match pattern: %s", subscription_name)
        raise ConfigurationException(
            "Subscription misconfigured. Expected subscriber_id to "
            f"match '{EXPECTED_SUBSCRIBER_REGEXP.pattern}' but was "
            f"'{subscription_name}'"
        )


def validate_topic_name(topic_name: str) -> None:
    """Validates that a topic name is correct.

    Raises ConfigurationException on failure.
    """
    if not EXPECTED_TOPIC_REGEXP.match(topic_name):
        DIAGNOSTICS.increment("topic_name_invalid")
        _LOGGER.debug("Topic name did not match pattern: %s", topic_name)
        raise ConfigurationException(
            "Subscription misconfigured. Expected topic name to "
            f"match '{EXPECTED_TOPIC_REGEXP.pattern}' but was "
            f"'{topic_name}'."
        )


def validate_projects_prefix(project_path: str) -> None:
    """Validates that a topic or subscription prefix is correct.

    Raises ConfigurationException on failure.
    """
    if not EXPECTED_PROJECS_PREFIX.match(project_path):
        DIAGNOSTICS.increment("topic_prefix_invalid")
        _LOGGER.debug("Topic prefix did not match pattern: %s", project_path)
        raise ConfigurationException(
            "Subscription misconfigured. Expected topic name to "
            f"match '{EXPECTED_PROJECS_PREFIX.pattern}' but was "
            f"'{project_path}'."
        )


class AdminClient:
    """Admin client for the Google Nest SDM API."""

    def __init__(
        self,
        auth: AbstractAuth,
        cloud_project_id: str,
    ) -> None:
        """Initialize the admin client.

        The auth instance must be configured with the correct host (PUBSUB_API_HOST).
        """
        self._cloud_project_id = cloud_project_id
        self._auth = auth

    async def create_topic(self, topic_name: str) -> None:
        """Create a pubsub topic for the project."""
        validate_topic_name(topic_name)
        await self._auth.put(topic_name)

    async def delete_topic(self, topic_name: str) -> None:
        """Delete a pubsub topic for the project."""
        validate_topic_name(topic_name)
        await self._auth.delete(topic_name)

    async def list_topics(self, projects_prefix: str) -> list[str]:
        """List the pubsub topics for the project.

        The topic prefix should be in the format `projects/{console_project_id}`.
        """
        validate_projects_prefix(projects_prefix)
        response = await self._auth.get_json(f"{projects_prefix}/topics")
        return [topic["name"] for topic in response.get("topics", ())]

    async def get_topic(self, topic_name: str) -> dict[str, Any]:
        """Get a pubsub topic for the project."""
        validate_topic_name(topic_name)
        return await self._auth.get_json(topic_name)

    async def set_topic_iam_policy(
        self, topic_name: str, policy: dict[str, Any]
    ) -> None:
        """Create a pubsub topic for the project."""
        validate_topic_name(topic_name)
        path = f"{topic_name}:setIamPolicy"
        await self._auth.post(path, json={"policy": policy})

    async def create_subscription(
        self, topic_name: str, subscription_name: str
    ) -> None:
        """Create a pubsub subscription for the project."""
        validate_topic_name(topic_name)
        validate_subscription_name(subscription_name)
        body = {"topic": topic_name}
        await self._auth.put(subscription_name, json=body)

    async def delete_subscription(self, subscription_name: str) -> None:
        """Delete a pubsub subscription for the project."""
        validate_subscription_name(subscription_name)
        await self._auth.delete(subscription_name)

    async def list_subscriptions(self, projects_prefix: str) -> list[dict[str, Any]]:
        """List the pubsub subscriptions for the project.
        The projects_prefix should be in the format `projects/{console_project_id}`.
        """
        validate_projects_prefix(projects_prefix)
        response = await self._auth.get_json(f"{projects_prefix}/subscriptions")
        return response.get("subscriptions", [])  # type: ignore[no-any-return]

    async def list_eligible_topics(
        self, device_access_project_id: str
    ) -> EligibleTopics:
        """List the eligible topics for the project.

        This will try to find any topics already created for the project by either
        the device access console or by the user.
        """

        sdm_topic_name = SDM_MANAGED_TOPIC_FORMAT.format(
            device_access_project_id=device_access_project_id
        )

        async def get_sdm_topic() -> str | None:
            try:
                await self.get_topic(sdm_topic_name)
            except ApiForbiddenException:
                _LOGGER.debug(
                    "SDM topic exists but we do not have permission to access it (expected)"
                )
                # The SDM topic exists. It is normal that we do not have permission
                # to access it.
                return sdm_topic_name
            except NotFoundException:
                _LOGGER.debug(
                    "SDM topic does not exist, proceeding to check cloud projects"
                )
                return None
            except ApiException as err:
                _LOGGER.info(
                    "Unexpected error retrieving an SDM created topic: %s", err
                )
                raise ApiException("Error retrieving SDM created topic") from err
            _LOGGER.debug(
                "SDM topic exists and we have permission to access it (unexpected)"
            )
            return sdm_topic_name

        async def get_cloud_topics() -> list[str]:
            try:
                return await self.list_topics(f"projects/{self._cloud_project_id}")
            except ApiException as err:
                _LOGGER.info("Unexpected error listing topics: %s", err)
                raise ApiException(
                    "Error while listing existing cloud console topics"
                ) from err

        (sdm_topic_task, cloud_topics_task) = await asyncio.gather(
            get_sdm_topic(), get_cloud_topics()
        )
        topics = []
        if sdm_topic_task:
            topics.append(sdm_topic_task)
        topics.extend(cloud_topics_task)
        return EligibleTopics(topic_names=topics)

    async def list_eligible_subscriptions(
        self, expected_topic_name: str
    ) -> EligibleSubscriptions:
        """Return a set of eligible subscriptions for the project."""
        subscriptions = await self.list_subscriptions(
            f"projects/{self._cloud_project_id}"
        )
        return EligibleSubscriptions(
            subscription_names=[
                sub["name"]
                for sub in subscriptions
                if sub["topic"] == expected_topic_name
            ]
        )
