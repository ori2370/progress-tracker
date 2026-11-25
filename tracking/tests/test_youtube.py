import io
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from tracking.models import ExerciseDefinition
from tracking.services.youtube import (
    YouTubeSearchError,
    format_video_duration,
    search_exercise_videos,
)


@override_settings(YOUTUBE_API_KEY="test-key")
class YouTubeServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_duration_formatting(self):
        cases = {
            "PT2M14S": "2:14",
            "PT15M30S": "15:30",
            "PT1H2M3S": "1:02:03",
            "PT45S": "0:45",
            "": "Duration unavailable",
            "invalid": "Duration unavailable",
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(
                    format_video_duration(value),
                    expected,
                )

    @override_settings(YOUTUBE_API_KEY="")
    @patch("tracking.services.youtube.urlopen")
    def test_missing_key_does_not_contact_youtube(self, mock_open):
        with self.assertRaisesMessage(
            YouTubeSearchError,
            "not configured",
        ):
            search_exercise_videos("Leg press")

        mock_open.assert_not_called()

    @patch("tracking.services.youtube.urlopen")
    def test_search_includes_duration_and_caches_complete_results(
        self,
        mock_open,
    ):
        search_payload = {
            "items": [{
                "id": {"videoId": "abcdefghijk"},
                "snippet": {
                    "title": "Leg press &amp; technique",
                    "channelTitle": "Example channel",
                },
            }],
        }
        duration_payload = {
            "items": [{
                "id": "abcdefghijk",
                "contentDetails": {"duration": "PT2M14S"},
            }],
        }

        mock_open.side_effect = [
            io.BytesIO(json.dumps(search_payload).encode()),
            io.BytesIO(json.dumps(duration_payload).encode()),
        ]

        first = search_exercise_videos("Leg press")
        second = search_exercise_videos("Leg press")

        self.assertEqual(first, second)
        self.assertEqual(first[0]["duration"], "2:14")
        self.assertEqual(first[0]["title"], "Leg press & technique")
        self.assertEqual(
            first[0]["url"],
            "https://www.youtube.com/watch?v=abcdefghijk",
        )
        self.assertEqual(mock_open.call_count, 2)

    @patch("tracking.services.youtube.urlopen")
    def test_quota_error_has_a_friendly_message(self, mock_open):
        mock_open.side_effect = HTTPError(
            "https://www.googleapis.com/youtube/v3/search",
            403,
            "Forbidden",
            {},
            None,
        )

        with self.assertRaisesMessage(
            YouTubeSearchError,
            "quota",
        ):
            search_exercise_videos("Leg press")

    @patch("tracking.services.youtube.urlopen")
    def test_network_failure_has_a_friendly_message(self, mock_open):
        mock_open.side_effect = URLError("Network unavailable")

        with self.assertRaisesMessage(
            YouTubeSearchError,
            "Could not reach YouTube",
        ):
            search_exercise_videos("Leg press")

    @patch("tracking.services.youtube.urlopen")
    def test_duration_failure_keeps_video_suggestions(self, mock_open):
        payload = {
            "items": [{
                "id": {"videoId": "abcdefghijk"},
                "snippet": {
                    "title": "Leg press",
                    "channelTitle": "Example channel",
                },
            }],
        }

        mock_open.side_effect = [
            io.BytesIO(json.dumps(payload).encode()),
            URLError("Network unavailable"),
        ]

        videos = search_exercise_videos("Leg press")

        self.assertEqual(len(videos), 1)
        self.assertEqual(
            videos[0]["duration"],
            "Duration unavailable",
        )


class ExerciseVideoSearchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="video-owner")
        self.other_user = User.objects.create_user(username="video-other")
        self.exercise = ExerciseDefinition.objects.create(
            user=self.owner,
            name="Leg press",
        )
        self.url = reverse(
            "tracking:exercise-video-search",
            kwargs={"pk": self.exercise.pk},
        )

    @patch("tracking.views.videos.search_exercise_videos")
    def test_login_is_required(self, mock_search):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        mock_search.assert_not_called()

    @patch("tracking.views.videos.search_exercise_videos")
    def test_other_users_cannot_search_for_owners_exercise(
        self,
        mock_search,
    ):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
        mock_search.assert_not_called()

    @patch("tracking.views.videos.search_exercise_videos")
    def test_owner_receives_suggestions(self, mock_search):
        self.client.force_login(self.owner)
        mock_search.return_value = [{
            "id": "abcdefghijk",
            "duration": "2:14",
        }]

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["videos"][0]["duration"],
            "2:14",
        )
        mock_search.assert_called_once_with("Leg press")

    @patch("tracking.views.videos.search_exercise_videos")
    def test_search_error_returns_503(self, mock_search):
        self.client.force_login(self.owner)
        mock_search.side_effect = YouTubeSearchError(
            "Search temporarily unavailable."
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"error": "Search temporarily unavailable."},
        )