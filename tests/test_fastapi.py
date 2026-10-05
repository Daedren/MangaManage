import asyncio
from contextlib import contextmanager
import unittest
from unittest.mock import MagicMock, call, patch

from API import fastapi


class TestMangaUpdatesEndpoint(unittest.TestCase):
    def test_latestChapterResponse(self):
        with patch.object(fastapi, "mangaupd_gateway") as gateway:
            gateway.getLatestChapterForId.return_value = 42
            result = asyncio.run(fastapi.get_latest_releases(123))
            self.assertEqual(result, {"series_id": 123, "latest_chapter": 42})
            gateway.getLatestChapterForId.assert_called_once_with(123)

    def test_unknownChapterResponse(self):
        with patch.object(fastapi, "mangaupd_gateway") as gateway:
            gateway.getLatestChapterForId.return_value = None
            self.assertEqual(asyncio.run(fastapi.get_latest_releases(123)),
                             {"series_id": 123, "latest_chapter": None})

    def test_upstreamFailureReturnsError(self):
        with patch.object(fastapi, "mangaupd_gateway") as gateway:
            gateway.getLatestChapterForId.side_effect = RuntimeError("request failed")
            with self.assertRaises(fastapi.HTTPException) as error:
                asyncio.run(fastapi.get_latest_releases(123))
            self.assertEqual(error.exception.status_code, 500)


@contextmanager
def no_op_log_capture(*args, **kwargs):
    yield


class TestDeleteChapterEndpoint(unittest.TestCase):
    def setUp(self):
        self.database = MagicMock()
        self.filesystem = MagicMock()
        self.original_database = fastapi.database_gateway
        self.original_filesystem = fastapi.filesystem_gateway
        self.original_log_capture = fastapi.capture_last_run_logs
        fastapi.database_gateway = self.database
        fastapi.filesystem_gateway = self.filesystem
        fastapi.capture_last_run_logs = no_op_log_capture

    def tearDown(self):
        fastapi.database_gateway = self.original_database
        fastapi.filesystem_gateway = self.original_filesystem
        fastapi.capture_last_run_logs = self.original_log_capture

    def test_delete_chapter_deletes_archive_before_soft_deleting_database_record(self):
        chapter = {"anilistId": 123, "chapter": "4.5"}
        self.database.getChapterDetailsById.return_value = chapter
        operations = MagicMock()
        operations.attach_mock(self.filesystem.deleteArchive, "delete_archive")
        operations.attach_mock(self.database.deleteChapterById, "soft_delete")

        asyncio.run(fastapi.delete_chapter(42))

        self.filesystem.deleteArchive.assert_called_once_with(123, "4.5")
        self.database.deleteChapterById.assert_called_once_with(42)
        self.assertEqual(
            operations.mock_calls,
            [
                call.delete_archive(123, "4.5"),
                call.soft_delete(42),
            ],
        )

    def test_delete_chapter_soft_deletes_when_database_record_is_missing(self):
        self.database.getChapterDetailsById.return_value = None

        asyncio.run(fastapi.delete_chapter(42))

        self.filesystem.deleteArchive.assert_not_called()
        self.database.deleteChapterById.assert_called_once_with(42)
