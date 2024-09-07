# SDP Direction Constants
DIRECTION_SENDRECV = 'sendrecv'
DIRECTION_SENDONLY = 'sendonly'
DIRECTION_RECVONLY = 'recvonly'
DIRECTION_INACTIVE = 'inactive'

AVAILABLE_DIRECTIONS = [DIRECTION_SENDRECV,
                        DIRECTION_SENDONLY,
                        DIRECTION_RECVONLY,
                        DIRECTION_INACTIVE]


class WebRTCUtility:
    """
    This class provides methods for managing WebRTC SDP.
    """

    def get_media_direction(self, sdp, kind):
        """
        Retrieves the direction of media tracks from the SDP based on the kind (audio/video).

        Args:
            sdp (str): The SDP content
            kind (str): The kind of media track to check ('audio' or 'video').

        Returns:
            str: The direction of the media track. One of 'sendrecv', 'sendonly', 'recvonly', or 'inactive'.
        """
        # Split the SDP into lines
        lines = sdp.splitlines()

        # Variable to track if we are in the desired media section
        in_media_section = False

        # Search for the media type and direction
        for line in lines:
            # Check if the line is a media description line (m=)
            if line.startswith('m='):
                in_media_section = (kind in line)

            # If we're in the desired media section, check for direction
            if in_media_section:
                for direction in AVAILABLE_DIRECTIONS:
                    if line.startswith(f'a={direction}'):
                        return direction
        return None

    def update_direction_in_answer(self, answer_sdp, kind, old_direction, new_direction):
        """
        Updates the direction of a specific media track in the SDP answer if it matches a certain direction.

        Args:
            answer_sdp (str): The SDP answer in string format.
            kind (str): The kind of media track to update ('audio' or 'video').
            old_direction (str): The old direction to find ('sendrecv', 'sendonly', 'recvonly', 'inactive').
            new_direction (str): The new direction to set ('sendrecv', 'sendonly', 'recvonly', 'inactive').

        Returns:
            str: The updated SDP with the new direction.
        """

        # Update the SDP
        sdp_lines = answer_sdp.split('\r\n')
        updated_sdp_lines = []
        in_media_section = False

        for line in sdp_lines:
            if line.startswith('m='):
                in_media_section = (kind in line)
            if in_media_section and line.startswith('a='):
                # Update the direction line if it matches the kind
                if line.startswith(f'a={old_direction}'):
                    updated_sdp_lines.append(f'a={new_direction}')
                    continue
            updated_sdp_lines.append(line)

        updated_sdp = '\r\n'.join(updated_sdp_lines)
        return updated_sdp

    def add_foundation_to_candidates(self, sdp):
        """
        Adds a foundation value to all ICE candidates in the SDP if it does not already exist.

        Args:
            sdp (str): The SDP in string format.

        Returns:
            str: The updated SDP with the foundation value added to ICE candidates.
        """
        # Add the foundation value to each ICE candidate line
        updated_sdp = sdp
        index = 1
        for line in sdp.split("\r\n"):
            if line.startswith("a=candidate: "):
                updated_sdp = updated_sdp.replace(line, line.replace(
                    "a=candidate: ", "a=candidate:"+str(index)+" "))
                index += 1
        return updated_sdp

    def fix_mozilla_sdp_answer(self, offer_sdp, answer_sdp):
        """Fix the answer SDP which is rejected by Firefox.

        1. If offer SDP is recvonly, the direction of answer SDP must not be sendrecv.
        2. If the ICE candidates in answer SDP must contain "foundation" field.
        """
        if self.get_media_direction(sdp=offer_sdp, kind="video") == DIRECTION_RECVONLY:
            answer_sdp = self.update_direction_in_answer(
                answer_sdp=answer_sdp, kind="video", old_direction=DIRECTION_SENDRECV, new_direction=DIRECTION_SENDONLY)
        if self.get_media_direction(sdp=offer_sdp, kind="audio") == DIRECTION_RECVONLY:
            answer_sdp = self.update_direction_in_answer(
                answer_sdp=answer_sdp, kind="audio", old_direction=DIRECTION_SENDRECV, new_direction=DIRECTION_SENDONLY)

        answer_sdp = self.add_foundation_to_candidates(answer_sdp)
        return answer_sdp
