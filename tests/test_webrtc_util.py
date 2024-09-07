"""Tests for WebRTC utility."""

import pytest
from google_nest_sdm.webrtc_util import DIRECTION_SENDONLY, DIRECTION_SENDRECV, WebRTCUtility


@pytest.fixture
def utility():
    """
    Fixture to create a WebRTCUtility instance for testing.
    """
    return WebRTCUtility()

def test_get_media_direction(utility: WebRTCUtility):
    """
    Test getting the direction in the SDP.
    """
    sdp = (
        "v=0\r\n"
        "o=- 123456 654321 IN IP4 127.0.0.1\r\n"
        "s=Test\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 49170 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=sendrecv\r\n"  # Existing direction
        "m=video 51372 RTP/AVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=sendrecv\r\n"
    )
    
    direction = utility.get_media_direction(sdp, 'audio')

    assert direction == DIRECTION_SENDRECV

def test_update_direction_in_answer(utility):
    """
    Test updating the direction in the SDP answer.
    """
    original_sdp = (
        "v=0\r\n"
        "o=- 123456 654321 IN IP4 127.0.0.1\r\n"
        "s=Test\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 49170 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=sendrecv\r\n"  # Existing direction
        "m=video 51372 RTP/AVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=sendrecv\r\n"
    )

    # Expected result after changing the audio direction
    expected_sdp = (
        "v=0\r\n"
        "o=- 123456 654321 IN IP4 127.0.0.1\r\n"
        "s=Test\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 49170 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=sendonly\r\n"  # Updated direction
        "m=video 51372 RTP/AVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=sendrecv\r\n"
    )

    new_sdp = utility.update_direction_in_answer(
        original_sdp, 'audio', DIRECTION_SENDRECV, DIRECTION_SENDONLY)

    assert new_sdp == expected_sdp


def test_add_foundation_to_candidates(utility):
    """
    Test adding a foundation value to ICE candidates.
    """
    original_sdp = (
        "v=0\r\n"
        "o=- 123456 654321 IN IP4 127.0.0.1\r\n"
        "s=Test\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "a=candidate: 1 UDP 2122260223 192.168.0.1 49170 typ host\r\n"
        "a=candidate: 1 UDP 2122260223 192.168.0.1 51372 typ host\r\n"
    )

    expected_sdp = (
        "v=0\r\n"
        "o=- 123456 654321 IN IP4 127.0.0.1\r\n"
        "s=Test\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "a=candidate:1 1 UDP 2122260223 192.168.0.1 49170 typ host\r\n"
        "a=candidate:2 1 UDP 2122260223 192.168.0.1 51372 typ host\r\n"
    )

    new_sdp = utility.add_foundation_to_candidates(original_sdp)

    assert new_sdp == expected_sdp
