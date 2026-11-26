from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tracking.models import MatchSet, TennisSession


class TennisResultTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="match-owner",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-match-owner",
        )
        self.client.force_login(self.user)

        self.session = TennisSession.objects.create(
            user=self.user,
            date=timezone.localdate(),
            session_type="match",
            focus="Test match",
            match_result="unfinished",
        )
        self.url = reverse(
            "tracking:tennis-result-update",
            args=[self.session.pk],
        )

    def score_data(self, result, scores):
        data = {
            "match_result": result,
            "set_count": str(len(scores)),
            "sets-TOTAL_FORMS": "5",
            "sets-INITIAL_FORMS": "0",
            "sets-MIN_NUM_FORMS": "0",
            "sets-MAX_NUM_FORMS": "5",
        }

        for index, (mine, theirs) in enumerate(scores):
            data[f"sets-{index}-my_games"] = str(mine)
            data[f"sets-{index}-opponent_games"] = str(theirs)

        return data

    def test_result_and_scores_are_saved(self):
        response = self.client.post(
            self.url,
            self.score_data("won", [(6, 3), (6, 4)]),
        )

        self.assertRedirects(
            response,
            reverse("tracking:tennis-list"),
        )
        self.session.refresh_from_db()

        self.assertEqual(self.session.match_result, "won")
        self.assertEqual(
            list(
                self.session.sets.order_by("number").values_list(
                    "number", "my_games", "opponent_games"
                )
            ),
            [(1, 6, 3), (2, 6, 4)],
        )

        response = self.client.get(self.url)
        self.assertEqual(
            response.context["set_formset"].forms[0]["my_games"].value(),
            6,
        )

    def test_set_count_can_be_reduced_or_cleared(self):
        for number in range(1, 4):
            MatchSet.objects.create(
                session=self.session,
                number=number,
                my_games=6,
                opponent_games=3,
            )

        response = self.client.post(
            self.url,
            self.score_data("won", [(6, 2), (6, 4)]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.session.sets.count(), 2)

        response = self.client.post(
            self.url,
            self.score_data("unfinished", []),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.session.sets.exists())

    def test_invalid_tiebreak_preserves_existing_result_and_scores(self):
        MatchSet.objects.create(
            session=self.session,
            number=1,
            my_games=6,
            opponent_games=3,
        )

        response = self.client.post(
            self.url,
            self.score_data("won", [(7, 6)]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["set_formset"].forms[0].errors
        )

        self.session.refresh_from_db()
        self.assertEqual(self.session.match_result, "unfinished")
        self.assertEqual(
            self.session.sets.get(number=1).opponent_games,
            3,
        )

    def test_other_user_cannot_read_or_update_result(self):
        self.client.force_login(self.other_user)

        self.assertEqual(self.client.get(self.url).status_code, 404)

        response = self.client.post(
            self.url,
            self.score_data("won", [(6, 0)]),
        )

        self.assertEqual(response.status_code, 404)
        self.session.refresh_from_db()
        self.assertEqual(self.session.match_result, "unfinished")
        self.assertFalse(self.session.sets.exists())

    def test_active_matches_and_nonmatches_are_unavailable(self):
        self.session.status = "in_progress"
        self.session.started_at = timezone.now()
        self.session.save()

        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.session.status = "completed"
        self.session.session_type = "practice"
        self.session.save()

        self.assertEqual(self.client.get(self.url).status_code, 404)