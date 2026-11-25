from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import MatchSet, TennisSession


class TennisSessionAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(username="owner")
        self.other_user = User.objects.create_user(username="other")

        self.session = TennisSession.objects.create(
            user=self.owner,
            date=date(2026, 10, 28),
            session_type=TennisSession.SessionType.PRACTICE,
            focus="Forehand contact",
        )

    def test_login_required(self):
        for name in ("tennis-list", "tennis-create"):
            with self.subTest(page=name):
                response = self.client.get(
                    reverse(f"tracking:{name}")
                )

                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    response.url.startswith("/admin/login/")
                )

    def test_owner_can_see_their_session(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("tracking:tennis-list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forehand contact")

    def test_other_user_cannot_see_session(self):
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse("tracking:tennis-list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["sessions"]),
            [],
        )

    def test_creation_assigns_signed_in_user(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("tracking:tennis-create"),
            {
                "date": "2026-10-28",
                "session_type": "lesson",
                "focus": "Serve preparation",
                "user": self.other_user.pk,
                "sets-TOTAL_FORMS": "5",
                "sets-INITIAL_FORMS": "0",
                "sets-MIN_NUM_FORMS": "0",
                "sets-MAX_NUM_FORMS": "5",
            },
        )

        self.assertRedirects(
            response,
            reverse("tracking:tennis-list"),
        )

        session = TennisSession.objects.get(
            focus="Serve preparation"
        )
        self.assertEqual(session.user, self.owner)

    def test_delete_requires_login(self):
        response = self.client.post(
            reverse("tracking:tennis-delete"),
            {
                "sessions": [self.session.pk],
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith("/admin/login/")
        )
        self.assertTrue(
            TennisSession.objects.filter(
                pk=self.session.pk
            ).exists()
        )

    def test_selection_preview_does_not_delete(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("tracking:tennis-delete"),
            {
                "sessions": [self.session.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forehand contact")
        self.assertTrue(
            TennisSession.objects.filter(
                pk=self.session.pk
            ).exists()
        )

    def test_owner_can_delete_multiple_sessions_and_sets(self):
        self.client.force_login(self.owner)

        match = TennisSession.objects.create(
            user=self.owner,
            date=date(2026, 10, 28),
            session_type=TennisSession.SessionType.MATCH,
            focus="Sample match",
            match_result=TennisSession.MatchResult.WON,
        )

        match_set = MatchSet.objects.create(
            session=match,
            number=1,
            my_games=6,
            opponent_games=4,
        )

        # This session must survive because it is not selected.
        unselected_session = TennisSession.objects.create(
            user=self.owner,
            date=date(2026, 10, 29),
            session_type=TennisSession.SessionType.PRACTICE,
            focus="Keep this practice",
        )

        response = self.client.post(
            reverse("tracking:tennis-delete"),
            {
                "sessions": [self.session.pk, match.pk],
                "action": "confirm",
            },
        )

        self.assertRedirects(
            response,
            reverse("tracking:tennis-list"),
        )
        self.assertFalse(
            TennisSession.objects.filter(
                pk__in=[self.session.pk, match.pk]
            ).exists()
        )
        self.assertFalse(
            MatchSet.objects.filter(
                pk=match_set.pk
            ).exists()
        )
        self.assertTrue(
            TennisSession.objects.filter(
                pk=unselected_session.pk
            ).exists()
        )

    def test_mixed_ownership_selection_deletes_nothing(self):
        self.client.force_login(self.owner)

        other_session = TennisSession.objects.create(
            user=self.other_user,
            date=date(2026, 10, 28),
            session_type=TennisSession.SessionType.PRACTICE,
            focus="Other user's practice",
        )

        response = self.client.post(
            reverse("tracking:tennis-delete"),
            {
                "sessions": [
                    self.session.pk,
                    other_session.pk,
                ],
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            TennisSession.objects.filter(
                pk__in=[
                    self.session.pk,
                    other_session.pk,
                ]
            ).count(),
            2,
        )

    def test_empty_selection_is_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("tracking:tennis-delete"),
            {
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            TennisSession.objects.filter(
                pk=self.session.pk
            ).exists()
        )

    def test_get_request_does_not_delete(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("tracking:tennis-delete"),
            {
                "sessions": [self.session.pk],
                "action": "confirm",
            },
        )

        self.assertRedirects(
            response,
            reverse("tracking:tennis-list"),
        )
        self.assertTrue(
            TennisSession.objects.filter(
                pk=self.session.pk
            ).exists()
        )

    def test_filter_by_session_type(self):
        self.client.force_login(self.owner)

        lesson = TennisSession.objects.create(
            user=self.owner,
            date=date(2026, 10, 29),
            session_type=TennisSession.SessionType.LESSON,
            focus="Serve lesson",
        )

        TennisSession.objects.create(
            user=self.other_user,
            date=date(2026, 10, 29),
            session_type=TennisSession.SessionType.LESSON,
            focus="Private lesson",
        )

        response = self.client.get(
            reverse("tracking:tennis-list"),
            {
                "session_type": "lesson",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["sessions"]),
            [lesson],
        )

    def test_sort_by_date(self):
        self.client.force_login(self.owner)

        later_session = TennisSession.objects.create(
            user=self.owner,
            date=date(2026, 10, 29),
            session_type=TennisSession.SessionType.PRACTICE,
            focus="Later practice",
        )

        cases = {
            "oldest": [self.session, later_session],
            "newest": [later_session, self.session],
        }

        for sort, expected in cases.items():
            with self.subTest(sort=sort):
                response = self.client.get(
                    reverse("tracking:tennis-list"),
                    {
                        "sort": sort,
                    },
                )

                self.assertEqual(
                    list(response.context["sessions"]),
                    expected,
                )

    def test_invalid_filters_use_defaults(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("tracking:tennis-list"),
            {
                "session_type": "unknown",
                "sort": "unknown",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_type"],
            "",
        )
        self.assertEqual(
            response.context["selected_sort"],
            "newest",
        )
        self.assertEqual(
            list(response.context["sessions"]),
            [self.session],
        )