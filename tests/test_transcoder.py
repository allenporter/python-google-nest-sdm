import asyncio
from unittest.mock import Mock, patch

import pytest

from google_nest_sdm.exceptions import TranscodeException
from google_nest_sdm.transcoder import Transcoder

BINARY = "/bin/true"


async def test_transcoder_file_not_exist(tmp_path: str) -> None:
    t = Transcoder(BINARY, path_prefix=tmp_path)
    with pytest.raises(TranscodeException):
        await t.transcode_clip("in_file.mp4", "out_file.gif")


async def test_transcoder_output_already_exists(tmp_path: str) -> None:
    t = Transcoder(BINARY, path_prefix=tmp_path)
    with open(f"{tmp_path}/in_file.mp4", mode="w") as f:
        f.write("some-input")
    with open(f"{tmp_path}/out_file.gif", mode="w") as f:
        f.write("some-output")
    with pytest.raises(TranscodeException):
        await t.transcode_clip("in_file.mp4", "out_file.gif")


async def test_transcoder(tmp_path: str) -> None:
    t = Transcoder(BINARY, path_prefix=tmp_path)
    with open(f"{tmp_path}/in_file.mp4", mode="w") as f:
        f.write("some-input")
    with patch(
        "google_nest_sdm.transcoder.asyncio.create_subprocess_shell"
    ) as mock_shell:
        process_mock = Mock()
        future: asyncio.Future = asyncio.Future()
        future.set_result(("", ""))
        process_mock.communicate.return_value = future
        process_mock.returncode = 0
        mock_shell.return_value = process_mock
        await t.transcode_clip("in_file.mp4", "out_file.gif")


async def test_transcoder_failure(tmp_path: str) -> None:
    t = Transcoder("/bin/false", path_prefix=tmp_path)
    with open(f"{tmp_path}/in_file.mp4", mode="w") as f:
        f.write("some-input")
    with (
        patch(
            "google_nest_sdm.transcoder.asyncio.create_subprocess_shell"
        ) as mock_shell,
        pytest.raises(TranscodeException),
    ):
        process_mock = Mock()
        future: asyncio.Future = asyncio.Future()
        future.set_result(("", ""))
        process_mock.communicate.return_value = future
        process_mock.returncode = 1
        mock_shell.return_value = process_mock
        await t.transcode_clip("in_file.mp4", "out_file.gif")
