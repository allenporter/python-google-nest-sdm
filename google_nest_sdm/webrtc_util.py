"""Library with functions for manipulating WebRTC requests/responses."""
from enum import StrEnum

# SDP direction constants
class SDPDirection(StrEnum):
    SENDRECV = "sendrecv"
    SENDONLY = "sendonly"
    RECVONLY = "recvonly"
    INACTIVE = "inactive"

# SDP media kind constants
class SDPMediaKind(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"
    APPLICATION = "application"

def _get_media_direction(sdp: str, kind: SDPMediaKind) -> SDPDirection | None:
    """
    Retrieves the direction of media tracks from the SDP based on the kind (audio/video).

    Args:
        sdp (str): The SDP content
        kind (SDPMediaKind): The kind of media track to check ('audio' or 'video').

    Returns:
        SDPMediaKind: The direction of the media track. One of 'sendrecv', 'sendonly', 'recvonly', or 'inactive'.
    """
    # Track if we are in the desired media section
    in_media_section = False

    for line in sdp.splitlines():
        # Check if the line is a media description line
        if line.startswith("m="):
            in_media_section = line.startswith(f"m={kind}")
        # If we're in the desired media section, check for direction
        if in_media_section and line.startswith("a="):
            for direction in SDPDirection:
                if line.startswith(f"a={direction}"):
                    return direction
    return None


def _update_direction_in_answer(answer_sdp: str, kind: SDPMediaKind, old_direction: SDPDirection, new_direction: SDPDirection) -> str:
    """
    Updates the direction of a specific media track in the SDP answer if it matches a certain direction.

    Args:
        answer_sdp (str): The SDP answer in string format.
        kind (SDPMediaKind): The kind of media track to update ('audio' or 'video').
        old_direction (SDPDirection): The old direction to find ('sendrecv', 'sendonly', 'recvonly', 'inactive').
        new_direction (SDPDirection): The new direction to set ('sendrecv', 'sendonly', 'recvonly', 'inactive').

    Returns:
        str: The updated SDP with the new direction.
    """

    # Update the SDP
    updated_sdp_lines = []
    in_media_section = False
    for line in answer_sdp.split("\r\n"):
        if line.startswith("m="):
            in_media_section = line.startswith(f"m={kind}")
        if in_media_section and line.startswith("a="):
            # Update the direction line if it matches the kind
            if line.startswith(f"a={old_direction}"):
                updated_sdp_lines.append(f"a={new_direction}")
                continue
        updated_sdp_lines.append(line)
    return "\r\n".join(updated_sdp_lines)


def _add_foundation_to_candidates(sdp: str) -> str:
    """
    Adds a foundation value to all ICE candidates in the SDP if it does not already exist.

    Args:
        sdp (str): The SDP in string format.

    Returns:
        str: The updated SDP with the foundation value added to ICE candidates.
    """
    # Add the foundation value to each ICE candidate line if not exist
    updated_sdp_lines = []
    index = 1
    for line in sdp.split("\r\n"):
        if line.startswith("a=candidate: "):
            updated_sdp_lines.append(line.replace("a=candidate: ", f"a=candidate:{index} "))
            index += 1
            continue
        updated_sdp_lines.append(line)
    return "\r\n".join(updated_sdp_lines)


def fix_mozilla_sdp_answer(offer_sdp: str, answer_sdp: str) -> str:
    """Fix the answer SDP which is rejected by Firefox.

    1. If offer SDP is recvonly, the direction of answer SDP must not be sendrecv.
    2. If the ICE candidates in answer SDP must contain "foundation" field.
    """
    if "mozilla" in offer_sdp:
        if _get_media_direction(sdp=offer_sdp, kind=SDPMediaKind.VIDEO) == SDPDirection.RECVONLY:
            answer_sdp = _update_direction_in_answer(
                answer_sdp=answer_sdp, kind=SDPMediaKind.VIDEO, old_direction=SDPDirection.SENDRECV, new_direction=SDPDirection.SENDONLY)
        if _get_media_direction(sdp=offer_sdp, kind=SDPMediaKind.AUDIO) == SDPDirection.RECVONLY:
            answer_sdp = _update_direction_in_answer(
                answer_sdp=answer_sdp, kind=SDPMediaKind.AUDIO, old_direction=SDPDirection.SENDRECV, new_direction=SDPDirection.SENDONLY)
        return _add_foundation_to_candidates(answer_sdp)
    return answer_sdp
