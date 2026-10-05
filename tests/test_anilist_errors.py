import unittest
import json
from unittest.mock import MagicMock, patch

from manga.gateways.anilist import AnilistGateway
from manga.gateways.utils.exceptions import AnilistRequestException


class TestAnilistErrors(unittest.TestCase):
    def setUp(self):
        self.gateway = AnilistGateway("token", "123", "client")
        self.gateway.logger = MagicMock()

    def test_http_error_preserves_status(self):
        for status in (401, 403, 429, 503):
            with self.subTest(status=status):
                response = MagicMock(status=status)
                with self.assertRaises(AnilistRequestException) as caught:
                    self.gateway.handle_anilist_errors(response, {}, "query", {})
                self.assertEqual(caught.exception.status, status)

    def test_bulk_graphql_error_preserves_status(self):
        with patch.object(self.gateway, "_AnilistGateway__prepareRequest",
                          return_value={"errors": [{"message": "Too Many Requests", "status": 429}]}):
            with self.assertRaises(AnilistRequestException) as caught:
                self.gateway.getAllEntries()
        self.assertEqual(caught.exception.status, 429)

    def test_bulk_graphql_error_without_status(self):
        with patch.object(self.gateway, "_AnilistGateway__prepareRequest",
                          return_value={"errors": [{"message": "Query rejected"}]}):
            with self.assertRaises(AnilistRequestException) as caught:
                self.gateway.getAllEntries()
        self.assertIsNone(caught.exception.status)

    def test_empty_list_is_not_a_lookup_failure(self):
        with patch.object(self.gateway, "_AnilistGateway__prepareRequest",
                          return_value={"data": {"MediaListCollection": {"lists": []}}}):
            self.assertEqual(self.gateway.getAllEntries(), {})

    def test_failed_graphql_response_is_not_cached(self):
        response = MagicMock(status=200)
        response.read.side_effect = [
            json.dumps({"errors": [{"message": "Too Many Requests", "status": 429}]}).encode(),
            json.dumps({"data": {"MediaListCollection": {"lists": []}}}).encode(),
        ]
        connection = MagicMock()
        connection.getresponse.return_value = response
        with patch("manga.gateways.anilist.http.client.HTTPSConnection", return_value=connection) as connect:
            with self.assertRaises(AnilistRequestException):
                self.gateway.getAllEntries()
            self.assertEqual(self.gateway.getAllEntries(), {})
            # The successful bulk response is reused without another API request.
            self.assertEqual(self.gateway.getAllEntries(), {})
        self.assertEqual(connect.call_count, 2)
