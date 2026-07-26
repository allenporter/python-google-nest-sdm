"""Tests for the admin client library."""

from typing import Awaitable, Callable, Any
from http import HTTPStatus

import aiohttp
import pytest

from google_nest_sdm.admin_client import AdminClient
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.exceptions import (
    ApiException,
    ConfigurationException,
)

from .conftest import Recorder, FAKE_TOKEN

GOOGLE_CLOUD_CONSOLE_PROJECT_ID = "google-cloud-console-project-id"
DEVICE_ACCESS_PROJECT_ID = "device-access-project-id"


@pytest.fixture(name="admin_client")
def mock_admin_client(
    auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> Callable[[], Awaitable[AdminClient]]:
    async def _make_admin_client() -> AdminClient:
        mock_auth = await auth_client()
        return AdminClient(mock_auth, GOOGLE_CLOUD_CONSOLE_PROJECT_ID)

    return _make_admin_client


def new_handler(
    r: Recorder,
    responses: list[dict[str, Any]],
    token: str = FAKE_TOKEN,
    status: HTTPStatus = HTTPStatus.OK,
) -> Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.Response]]:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % token
        s = await request.text()
        r.request = await request.json() if s else {}
        return aiohttp.web.json_response(responses.pop(0), status=status)

    return handler


async def test_invalid_topic_format(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test creating a topic."""
    client = await admin_client()
    with pytest.raises(ConfigurationException):
        await client.create_topic("some-topic")


async def test_create_topic(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test creating a topic."""

    handler = new_handler(
        recorder,
        [{}],
    )
    app.router.add_put(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name", handler
    )

    client = await admin_client()
    await client.create_topic(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name"
    )

    assert recorder.request == {}


async def test_delete_topic(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test deleting a topic."""

    handler = new_handler(
        recorder,
        [{}],
    )
    app.router.add_delete(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name", handler
    )

    client = await admin_client()
    await client.delete_topic(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name"
    )

    assert recorder.request == {}


async def test_list_topics(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing topics."""

    handler = new_handler(
        recorder,
        [
            {
                "topics": [
                    {"name": "projects/project-id/topics/topic1"},
                    {"name": "projects/project-id/topics/topic2"},
                ]
            }
        ],
    )
    app.router.add_get(f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics", handler)

    client = await admin_client()
    topics = await client.list_topics(f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}")

    assert topics == [
        "projects/project-id/topics/topic1",
        "projects/project-id/topics/topic2",
    ]
    assert recorder.request == {}


async def test_list_topics_empty_response(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing topics."""

    handler = new_handler(
        recorder,
        [{}],
    )
    app.router.add_get(f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics", handler)

    client = await admin_client()
    topics = await client.list_topics(f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}")

    assert topics == []
    assert recorder.request == {}


async def test_list_topics_invalid_prefix(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing topics with an invalid prefix."""

    handler = new_handler(
        recorder,
        [
            {
                "topics": [
                    {"name": "projects/project-id/topics/topic1"},
                    {"name": "projects/project-id/topics/topic2"},
                ]
            }
        ],
    )
    app.router.add_get(f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics", handler)

    client = await admin_client()
    with pytest.raises(ConfigurationException):
        await client.list_topics("projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics")


async def test_get_topic(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test getting a topic."""

    handler = new_handler(
        recorder,
        [{"name": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name"}],
    )
    app.router.add_get(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name", handler
    )

    client = await admin_client()
    response = await client.get_topic(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name"
    )
    assert recorder.request == {}
    assert response == {
        "name": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name"
    }


async def test_create_subscription(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test creating a subscription."""

    handler = new_handler(
        recorder,
        [{}],
    )
    app.router.add_put(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription-name",
        handler,
    )

    client = await admin_client()
    await client.create_subscription(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name",
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription-name",
    )

    assert recorder.request == {
        "topic": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name"
    }


async def test_create_subscription_failure(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test creating a subscription."""

    handler = new_handler(
        recorder,
        [{}],
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )
    app.router.add_put(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription-name",
        handler,
    )

    client = await admin_client()
    with pytest.raises(
        ApiException, match=r"Internal Server Error response from API \(500\)"
    ):
        await client.create_subscription(
            f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name",
            f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription-name",
        )


async def test_delete_subscription(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test deleting a subscription."""

    handler = new_handler(
        recorder,
        [{}],
    )
    app.router.add_delete(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription-name",
        handler,
    )

    client = await admin_client()
    await client.delete_subscription(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription-name"
    )

    assert recorder.request == {}


async def test_list_subscriptions(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing subscriptions."""

    handler = new_handler(
        recorder,
        [
            {
                "subscriptions": [
                    {
                        "name": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription1"
                    },
                    {
                        "name": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription2"
                    },
                ]
            }
        ],
    )
    app.router.add_get(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions", handler
    )

    client = await admin_client()
    subscriptions = await client.list_subscriptions(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}"
    )

    assert subscriptions == [
        {
            "name": "projects/google-cloud-console-project-id/subscriptions/subscription1"
        },
        {
            "name": "projects/google-cloud-console-project-id/subscriptions/subscription2"
        },
    ]


async def test_list_subscriptions_empty_response(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing subscriptions."""

    handler = new_handler(
        recorder,
        [{}],
    )
    app.router.add_get(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions", handler
    )

    client = await admin_client()
    subscriptions = await client.list_subscriptions(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}"
    )

    assert subscriptions == []
    assert recorder.request == {}


async def test_invalid_subscription_format(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test creating a subscription."""
    client = await admin_client()
    with pytest.raises(ConfigurationException):
        await client.create_subscription(
            f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name",
            "some-subscription",
        )
    with pytest.raises(ConfigurationException):
        await client.create_subscription(
            "some-topic",
            f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/subscription-name",
        )


async def test_list_eligible_topics(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing eligible topics."""

    # SDM created pubsub topic exists (but is not visible, which is expected) exists
    sdm_handler = new_handler(
        recorder,
        [
            {
                "error": {
                    "code": 403,
                    "message": "User not authorized to perform this action.",
                    "status": "PERMISSION_DENIED",
                }
            },
        ],
        status=HTTPStatus.FORBIDDEN,
    )
    app.router.add_get(
        f"/projects/sdm-prod/topics/enterprise-{DEVICE_ACCESS_PROJECT_ID}", sdm_handler
    )
    # Cloud topic also exists
    cloud_handler = new_handler(
        recorder,
        [
            {
                "topics": [
                    {
                        "name": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/sdm-testing"
                    }
                ]
            }
        ],
    )
    app.router.add_get(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics", cloud_handler
    )

    client = await admin_client()
    eligible_topics = await client.list_eligible_topics(DEVICE_ACCESS_PROJECT_ID)
    assert eligible_topics.topic_names == [
        "projects/sdm-prod/topics/enterprise-device-access-project-id",
        "projects/google-cloud-console-project-id/topics/sdm-testing",
    ]


async def test_list_eligible_topics_no_sdm_topic(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing eligible topics when no SDM topic exists."""

    # SDM created pubsub topic does not exist
    sdm_handler = new_handler(
        recorder,
        [
            {
                "error": {
                    "code": 404,
                    "message": f"Resource not found (resource=enterprise-{DEVICE_ACCESS_PROJECT_ID}).",
                    "status": "NOT_FOUND",
                }
            }
        ],
        status=HTTPStatus.NOT_FOUND,
    )
    app.router.add_get(
        f"/projects/sdm-prod/topics/enterprise-{DEVICE_ACCESS_PROJECT_ID}", sdm_handler
    )

    # Cloud topic exists
    cloud_handler = new_handler(
        recorder,
        [
            {
                "topics": [
                    {
                        "name": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/sdm-testing"
                    }
                ]
            }
        ],
    )
    app.router.add_get(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics", cloud_handler
    )

    client = await admin_client()
    eligible_topics = await client.list_eligible_topics(DEVICE_ACCESS_PROJECT_ID)
    assert eligible_topics.topic_names == [
        "projects/google-cloud-console-project-id/topics/sdm-testing"
    ]


@pytest.mark.parametrize(
    "sdm_status, cloud_status",
    [
        (HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.OK),
        (HTTPStatus.OK, HTTPStatus.INTERNAL_SERVER_ERROR),
    ],
)
async def test_list_cloud_console_api_error(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
    sdm_status: HTTPStatus,
    cloud_status: HTTPStatus,
) -> None:
    """Test listing eligible topics when an error occurs listing the cloud console topics."""

    # SDM created pubsub topic exists (but is not visible, which is expected) exists
    sdm_handler = new_handler(
        recorder,
        [
            {
                "error": {
                    "code": 403,
                    "message": "User not authorized to perform this action.",
                    "status": "PERMISSION_DENIED",
                }
            },
        ],
        status=sdm_status,
    )
    app.router.add_get(
        f"/projects/sdm-prod/topics/enterprise-{DEVICE_ACCESS_PROJECT_ID}", sdm_handler
    )
    # Cloud topic also exists
    cloud_handler = new_handler(
        recorder,
        [{}],
        status=cloud_status,
    )
    app.router.add_get(f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}", cloud_handler)

    client = await admin_client()
    with pytest.raises(ApiException):
        await client.list_eligible_topics(DEVICE_ACCESS_PROJECT_ID)


async def test_list_eligible_subscriptions(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test listing eligible subscriptions."""

    cloud_handler = new_handler(
        recorder,
        [
            {
                "subscriptions": [
                    {
                        "name": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/sdm-testing-sub",
                        "topic": f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/sdm-testing",
                        "pushConfig": {},
                        "ackDeadlineSeconds": 10,
                        "messageRetentionDuration": "604800s",
                        "expirationPolicy": {"ttl": "2678400s"},
                        "state": "ACTIVE",
                    }
                ]
            }
        ],
    )
    app.router.add_get(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions", cloud_handler
    )

    client = await admin_client()
    eligible_subscriptions = await client.list_eligible_subscriptions(
        expected_topic_name=f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/sdm-testing"
    )
    assert eligible_subscriptions.subscription_names == [
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/subscriptions/sdm-testing-sub",
    ]


async def test_set_topic_iam_policy(
    app: aiohttp.web.Application,
    admin_client: Callable[[], Awaitable[AdminClient]],
    recorder: Recorder,
) -> None:
    """Test setting an IAM policy on a topic."""

    handler = new_handler(
        recorder,
        [{}],
    )
    app.router.add_post(
        f"/projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name:setIamPolicy",
        handler,
    )

    client = await admin_client()
    await client.set_topic_iam_policy(
        f"projects/{GOOGLE_CLOUD_CONSOLE_PROJECT_ID}/topics/topic-name",
        {"bindings": [{"role": "roles/pubsub.publisher", "members": ["user:foo"]}]},
    )

    assert recorder.request == {
        "policy": {
            "bindings": [{"role": "roles/pubsub.publisher", "members": ["user:foo"]}]
        }
    }
