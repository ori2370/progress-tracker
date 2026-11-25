from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..forms.focus import TennisFocusForm
from ..forms.tennis import TennisSessionForm
from ..models import TennisFocus, TennisSession


class TennisFocusTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="focus_owner")
        self.other = User.objects.create_user(username="focus_other")
        self.today = timezone.localdate()

        self.focus = TennisFocus.objects.create(
            user=self.owner,
            title="Backhand consistency",
            goal="Keep longer rallies going.",
            start_date=self.today - timedelta(days=7),
            end_date=self.today + timedelta(days=7),
            target_sessions=6,
        )

    def focus_data(self, **changes):
        data = {
            "title": "Serve placement",
            "goal": "Aim for a chosen area.",
            "start_date": self.today.isoformat(),
            "end_date": (self.today + timedelta(days=14)).isoformat(),
            "target_sessions": 4,
        }
        data.update(changes)
        return data

    def test_focus_pages_require_login(self):
        pages = [
            reverse("tracking:tennis-focus-list"),
            reverse("tracking:tennis-focus-create"),
            reverse(
                "tracking:tennis-focus-update",
                args=[self.focus.pk],
            ),
        ]

        for page in pages:
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/admin/login/"))

    def test_list_shows_only_owned_focuses(self):
        TennisFocus.objects.create(
            user=self.other,
            title="Private serve goal",
            start_date=self.today,
            end_date=self.today,
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("tracking:tennis-focus-list")
        )

        self.assertContains(response, self.focus.title)
        self.assertNotContains(response, "Private serve goal")

    def test_creation_assigns_signed_in_user(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("tracking:tennis-focus-create"),
            self.focus_data(user=self.other.pk),
        )

        self.assertRedirects(
            response,
            reverse("tracking:tennis-focus-list"),
        )
        focus = TennisFocus.objects.get(title="Serve placement")
        self.assertEqual(focus.user, self.owner)

    def test_owner_can_edit_focus(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "tracking:tennis-focus-update",
                args=[self.focus.pk],
            ),
            self.focus_data(title="Updated backhand goal"),
        )

        self.assertRedirects(
            response,
            reverse("tracking:tennis-focus-list"),
        )
        self.focus.refresh_from_db()
        self.assertEqual(self.focus.title, "Updated backhand goal")

    def test_other_user_cannot_view_or_edit_focus(self):
        self.client.force_login(self.other)
        url = reverse(
            "tracking:tennis-focus-update",
            args=[self.focus.pk],
        )

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(url, self.focus_data()).status_code,
            404,
        )

        self.focus.refresh_from_db()
        self.assertEqual(self.focus.title, "Backhand consistency")

    def test_end_date_cannot_precede_start_date(self):
        form = TennisFocusForm(
            data=self.focus_data(
                end_date=(self.today - timedelta(days=1)).isoformat()
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_session_target_is_optional_but_must_be_positive(self):
        for target in ("", 1, 6):
            with self.subTest(target=target):
                form = TennisFocusForm(
                    data=self.focus_data(target_sessions=target)
                )
                self.assertTrue(form.is_valid(), form.errors)

        for target in (0, -1):
            with self.subTest(target=target):
                form = TennisFocusForm(
                    data=self.focus_data(target_sessions=target)
                )
                self.assertFalse(form.is_valid())
                self.assertIn("target_sessions", form.errors)

    def test_session_form_rejects_another_users_focus(self):
        form = TennisSessionForm(
            user=self.other,
            data={
                "date": self.today.isoformat(),
                "session_type": "practice",
                "focus": "Backhand practice",
                "training_focus": self.focus.pk,
                "set_count": 0,
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("training_focus", form.errors)

    def test_progress_counts_only_linked_sessions_in_elapsed_period(self):
        dates = [
            self.focus.start_date,
            self.today,
            self.focus.start_date - timedelta(days=1),
            self.today + timedelta(days=1),
            self.focus.end_date + timedelta(days=1),
        ]

        for session_date in dates:
            TennisSession.objects.create(
                user=self.owner,
                training_focus=self.focus,
                date=session_date,
                session_type="practice",
                focus="Backhand practice",
            )

        TennisSession.objects.create(
            user=self.owner,
            date=self.today,
            session_type="practice",
            focus="Unlinked practice",
        )

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("tracking:tennis-focus-list")
        )
        focus = list(response.context["focuses"])[0]

        self.assertEqual(focus.completed_sessions, 2)
        self.assertEqual(focus.sessions_remaining, 4)

    def test_deleting_focus_preserves_session(self):
        session = TennisSession.objects.create(
            user=self.owner,
            training_focus=self.focus,
            date=self.today,
            session_type="practice",
            focus="Backhand practice",
        )

        self.focus.delete()
        session.refresh_from_db()

        self.assertIsNone(session.training_focus)