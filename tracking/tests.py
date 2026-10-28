from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import TennisSession


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
                response = self.client.get(reverse(f"tracking:{name}"))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/admin/login/"))

    def test_owner_can_see_their_session(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("tracking:tennis-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forehand contact")

    def test_other_user_cannot_see_session(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("tracking:tennis-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["sessions"]), [])

    def test_creation_assigns_signed_in_user(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("tracking:tennis-create"),
            {
                "date": "2026-10-28",
                "session_type": "lesson",
                "focus": "Serve preparation",
                "user": self.other_user.pk,
            },
        )

        self.assertRedirects(response, reverse("tracking:tennis-list"))
        session = TennisSession.objects.get(focus="Serve preparation")
        self.assertEqual(session.user, self.owner)