"""Library for transcoding mp4 clips."""

import asyncio.subprocess
import logging
import os

from .exceptions import TranscodeException

_LOGGER = logging.getLogger(__name__)


class Transcoder:
    """A worker that processes mp4 clips."""

    def __init__(self, ffmpeg_binary: str, path_prefix: str) -> None:
        """Initialize transcoder."""
        self._ffmpeg_binary = ffmpeg_binary
        self._path_prefix = path_prefix

    async def transcode_clip(self, input_file: str, output_file: str) -> None:
        """Create a image preview for a thumbnail clip."""
        full_input_file = f"{self._path_prefix}/{input_file}"
        full_output_file = f"{self._path_prefix}/{output_file}"
        if not os.path.exists(full_input_file):
            raise TranscodeException(f"Input file does not exist: {full_input_file}")
        if os.path.exists(full_output_file):
            raise TranscodeException(f"Output file already exists: {full_output_file}")
        cmd = " ".join(
            [
                self._ffmpeg_binary,
                "-y",
                "-i",
                full_input_file,
                "-vf setpts=2.0*PTS",
                "-vf scale=320:-1,setsar=1:1",
                "-r 4",
                "-loop 0",
                full_output_file,
            ]
        )
        proc = await asyncio.create_subprocess_shell(cmd)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            if stdout:
                _LOGGER.debug(stdout)
            if stderr:
                _LOGGER.debug(stderr)
            raise TranscodeException(
                f"Transcode command failure: {cmd} code: {proc.returncode}"
            )
