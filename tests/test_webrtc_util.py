"""Tests for WebRTC utility."""

from google_nest_sdm.webrtc_util import (
    SDPDirection,
    SDPMediaKind,
    _add_foundation_to_candidates,
    _get_media_direction,
    _update_direction_in_answer,
    fix_sdp_answer,
)


def test_fix_firefox_sdp_answer() -> None:
    """Test the fix in the SDP for Firefox."""
    firefox_offer_sdp = (
        "v=0\r\n"
        "o=mozilla...THIS_IS_SDPARTA-99.0 137092584186714854 0 IN IP4 0.0.0.0\r\n"
        "m=audio 9 UDP/TLS/RTP/SAVPF 109 9 0 8 101\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=recvonly\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 120 124 121 125 126 127 97 98 123 122 119\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=recvonly\r\n"
        "m=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=sendrecv\r\n"
    )
    answer_sdp = (
        "v=0\r\n"
        "o=- 0 2 IN IP4 127.0.0.1\r\n"
        "m=audio 19305 UDP/TLS/RTP/SAVPF 109\r\n"
        "c=IN IP4 74.125.247.118\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=candidate: 1 udp 2113939711 2001:4860:4864:4::118 19305 typ host generation 0\r\n"
        "a=candidate: 1 tcp 2113939710 2001:4860:4864:4::118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate: 1 ssltcp 2113939709 2001:4860:4864:4::118 443 typ host generation 0\r\n"
        "a=candidate: 1 udp 2113932031 74.125.247.118 19305 typ host generation 0\r\n"
        "a=candidate: 1 tcp 2113932030 74.125.247.118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate: 1 ssltcp 2113932029 74.125.247.118 443 typ host generation 0\r\n"
        "a=sendrecv\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 126 127\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=sendrecv\r\n"
        "m=application 9 DTLS/SCTP 5000\r\n"
        "c=IN IP4 0.0.0.0\r\n"
    )
    expected_firefox_answer_sdp = (
        "v=0\r\n"
        "o=- 0 2 IN IP4 127.0.0.1\r\n"
        "m=audio 19305 UDP/TLS/RTP/SAVPF 109\r\n"
        "c=IN IP4 74.125.247.118\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=candidate:1 1 udp 2113939711 2001:4860:4864:4::118 19305 typ host generation 0\r\n"
        "a=candidate:2 1 tcp 2113939710 2001:4860:4864:4::118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate:3 1 ssltcp 2113939709 2001:4860:4864:4::118 443 typ host generation 0\r\n"
        "a=candidate:4 1 udp 2113932031 74.125.247.118 19305 typ host generation 0\r\n"
        "a=candidate:5 1 tcp 2113932030 74.125.247.118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate:6 1 ssltcp 2113932029 74.125.247.118 443 typ host generation 0\r\n"
        "a=sendonly\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 126 127\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=sendonly\r\n"
        "m=application 9 DTLS/SCTP 5000\r\n"
        "c=IN IP4 0.0.0.0\r\n"
    )

    fixed_sdp = fix_sdp_answer(firefox_offer_sdp, answer_sdp)
    assert fixed_sdp == expected_firefox_answer_sdp


def test_fix_chrome_sdp_answer() -> None:
    """Test the fix in the SDP for Chrome."""
    chrome_offer_sdp = (
        "v=0\r\n"
        "o=- 6714414228100263102 2 IN IP4 127.0.0.1\r\n"
        "m=audio 9 UDP/TLS/RTP/SAVPF 111 63 9 0 8 13 110 126\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=recvonly\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 96 97 98 99 100 101 35 36 37 38 102 103 104 105 106 107 108 109 127 125 39 40 41 42 43 44 45 46 47 48 112 113 114 115 116 117 118 49\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=recvonly\r\n"
        "m=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n"
        "c=IN IP4 0.0.0.0\r\n"
    )
    answer_sdp = (
        "v=0\r\n"
        "o=- 0 2 IN IP4 127.0.0.1\r\n"
        "m=audio 19305 UDP/TLS/RTP/SAVPF 109\r\n"
        "c=IN IP4 74.125.247.118\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=candidate: 1 udp 2113939711 2001:4860:4864:4::118 19305 typ host generation 0\r\n"
        "a=candidate: 1 tcp 2113939710 2001:4860:4864:4::118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate: 1 ssltcp 2113939709 2001:4860:4864:4::118 443 typ host generation 0\r\n"
        "a=candidate: 1 udp 2113932031 74.125.247.118 19305 typ host generation 0\r\n"
        "a=candidate: 1 tcp 2113932030 74.125.247.118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate: 1 ssltcp 2113932029 74.125.247.118 443 typ host generation 0\r\n"
        "a=sendrecv\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 126 127\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=sendrecv\r\n"
        "m=application 9 DTLS/SCTP 5000\r\n"
        "c=IN IP4 0.0.0.0\r\n"
    )
    expected_chrome_answer_sdp = (
        "v=0\r\n"
        "o=- 0 2 IN IP4 127.0.0.1\r\n"
        "m=audio 19305 UDP/TLS/RTP/SAVPF 109\r\n"
        "c=IN IP4 74.125.247.118\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=candidate: 1 udp 2113939711 2001:4860:4864:4::118 19305 typ host generation 0\r\n"
        "a=candidate: 1 tcp 2113939710 2001:4860:4864:4::118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate: 1 ssltcp 2113939709 2001:4860:4864:4::118 443 typ host generation 0\r\n"
        "a=candidate: 1 udp 2113932031 74.125.247.118 19305 typ host generation 0\r\n"
        "a=candidate: 1 tcp 2113932030 74.125.247.118 19305 typ host tcptype passive generation 0\r\n"
        "a=candidate: 1 ssltcp 2113932029 74.125.247.118 443 typ host generation 0\r\n"
        "a=sendonly\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 126 127\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=rtcp:9 IN IP4 0.0.0.0\r\n"
        "a=sendonly\r\n"
        "m=application 9 DTLS/SCTP 5000\r\n"
        "c=IN IP4 0.0.0.0\r\n"
    )

    fixed_sdp = fix_sdp_answer(chrome_offer_sdp, answer_sdp)
    assert fixed_sdp == expected_chrome_answer_sdp


def test_get_media_direction() -> None:
    """Test getting the direction in the SDP."""
    sdp = (
        "v=0\r\n"
        "o=- 123456 654321 IN IP4 127.0.0.1\r\n"
        "s=Test\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 49170 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=sendrecv\r\n"
        "m=video 51372 RTP/AVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=sendonly\r\n"
    )

    direction = _get_media_direction(sdp, SDPMediaKind.AUDIO)
    assert direction == SDPDirection.SENDRECV
    direction = _get_media_direction(sdp, SDPMediaKind.VIDEO)
    assert direction == SDPDirection.SENDONLY
    direction = _get_media_direction(sdp, SDPMediaKind.APPLICATION)
    assert direction is None


def test_update_direction_in_answer() -> None:
    """Test updating the direction in the SDP answer."""
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

    new_sdp = _update_direction_in_answer(
        original_sdp, SDPMediaKind.AUDIO, SDPDirection.SENDRECV, SDPDirection.SENDONLY
    )

    assert new_sdp == expected_sdp


def test_add_foundation_to_candidates() -> None:
    """Test adding a foundation value to ICE candidates."""
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

    new_sdp = _add_foundation_to_candidates(original_sdp)

    assert new_sdp == expected_sdp
