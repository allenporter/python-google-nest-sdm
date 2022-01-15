import pytest

from google_nest_sdm.exceptions import TranscodeException
from google_nest_sdm.transcoder import Transcoder

BINARY = "/bin/echo"


async def test_transcoder() -> None:
    t = Transcoder("/bin/echo", path_prefix="/tmp")
    await t.transcode_clip("in_file.mp4", "out_file.gif")


async def test_transcoder_file_not_exists() -> None:
    t = Transcoder("/bin/echo", path_prefix="/tmp")
    await t.transcode_clip("in_file.mp4", "out_file.gif")


async def test_transcoder_failure() -> None:
    t = Transcoder("/bin/false", path_prefix="/tmp")
    with pytest.raises(TranscodeException):
        await t.transcode_clip("in_file.mp4", "out_file.gif")
