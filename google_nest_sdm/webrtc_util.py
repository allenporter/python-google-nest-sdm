"""Library with functions for manipulating WebRTC requests/responses."""

from enum import StrEnum


class SDPDirection(StrEnum):
    """SDP direction constants."""

    SENDRECV = "sendrecv"
    SENDONLY = "sendonly"
    RECVONLY = "recvonly"
    INACTIVE = "inactive"


class SDPMediaKind(StrEnum):
    """SDP media kind constants."""

    AUDIO = "audio"
    VIDEO = "video"
    APPLICATION = "application"


def _get_media_direction(sdp: str, kind: SDPMediaKind) -> SDPDirection | None:
    """Retrieves the direction of media tracks from the SDP based on the kind (audio/video)."""

    # Track if we are in the desired media section
    in_media_section = False

    for line in sdp.split("\r\n"):
        # Check if the line is a media description line
        if line.startswith("m="):
            in_media_section = line.startswith(f"m={kind}")
        # If we're in the desired media section, check for direction
        if in_media_section and line.startswith("a="):
            for direction in SDPDirection:
                if line.startswith(f"a={direction}"):
                    return direction
    return None


def _update_direction_in_answer(
    answer_sdp: str,
    kind: SDPMediaKind,
    old_direction: SDPDirection,
    new_direction: SDPDirection,
) -> str:
    """Updates the direction of a specific media track in the SDP answer if it matches a certain direction."""

    # Update the SDP
    updated_sdp_lines = []
    in_media_section = False
    for line in answer_sdp.split("\r\n"):
        if line.startswith("m="):
            in_media_section = line.startswith(f"m={kind}")
        if in_media_section and line.startswith("a="):
            # Update the direction line if it matches the kind
            if line.startswith(f"a={old_direction}"):
                updated_sdp_lines.append(
                    line.replace(f"a={old_direction}", f"a={new_direction}")
                )
                continue
        updated_sdp_lines.append(line)
    return "\r\n".join(updated_sdp_lines)


def _add_foundation_to_candidates(sdp: str) -> str:
    """Adds a foundation value to all ICE candidates in the SDP if it does not already exist."""

    updated_sdp_lines = []
    index = 1
    for line in sdp.split("\r\n"):
        if line.startswith("a=candidate: "):
            updated_sdp_lines.append(
                line.replace("a=candidate: ", f"a=candidate:{index} ")
            )
            index += 1
            continue
        updated_sdp_lines.append(line)
    return "\r\n".join(updated_sdp_lines)


def fix_sdp_answer(offer_sdp: str, answer_sdp: str) -> str:
    """Fix the answer SDP which is rejected by the browser

    For both firefox and chromium >= 143
    1. If offer SDP is recvonly, the direction of answer SDP must not be sendrecv.

    For firefox only
    1. If the ICE candidates in answer SDP must contain "foundation" field.
    """

    if (
        _get_media_direction(sdp=offer_sdp, kind=SDPMediaKind.VIDEO)
        == SDPDirection.RECVONLY
    ):
        answer_sdp = _update_direction_in_answer(
            answer_sdp=answer_sdp,
            kind=SDPMediaKind.VIDEO,
            old_direction=SDPDirection.SENDRECV,
            new_direction=SDPDirection.SENDONLY,
        )
    if (
        _get_media_direction(sdp=offer_sdp, kind=SDPMediaKind.AUDIO)
        == SDPDirection.RECVONLY
    ):
        answer_sdp = _update_direction_in_answer(
            answer_sdp=answer_sdp,
            kind=SDPMediaKind.AUDIO,
            old_direction=SDPDirection.SENDRECV,
            new_direction=SDPDirection.SENDONLY,
        )
    if "mozilla" in offer_sdp:
        return _add_foundation_to_candidates(answer_sdp)
    return answer_sdp
