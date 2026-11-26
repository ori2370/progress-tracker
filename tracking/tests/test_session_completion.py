from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tracking.forms.gym import GymWorkoutForm
from tracking.forms.tennis import TennisSessionForm
from tracking.models import GymWorkout, TennisSession


class SessionCompletionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="session-owner",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-session-owner",
        )
        self.client.force_login(self.user)

        self.now = timezone.now().replace(
            second=0,
            microsecond=0,
        )
        self.started = self.now - timedelta(hours=4)

        self.cases = [
            (
                GymWorkout,
                "gym-workout-finish",
                "gym-workout-times",
            ),
            (
                TennisSession,
                "tennis-finish",
                "tennis-times",
            ),
        ]

    def create_session(self, model, *, active=True):
        data = {
            "user": self.user,
            "date": timezone.localtime(self.started).date(),
        }

        if model is GymWorkout:
            data["title"] = "Test workout"
        else:
            data.update({
                "session_type": TennisSession.SessionType.PRACTICE,
                "focus": "Test practice",
            })

        if active:
            data.update({
                "status": "in_progress",
                "started_at": self.started,
            })

        return model.objects.create(**data)

    def local_input(self, value):
        return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")

    def test_live_gym_form_starts_timer(self):
        form = GymWorkoutForm(data={
            "recording_mode": "live",
            "date": timezone.localdate().isoformat(),
            "title": "Live workout",
            "notes": "",
        })
        form.instance.user = self.user

        self.assertTrue(form.is_valid(), form.errors)
        session = form.save()

        self.assertTrue(session.is_in_progress)
        self.assertIsNotNone(session.started_at)
        self.assertIsNone(session.finished_at)

    def test_live_tennis_match_does_not_require_result(self):
        form = TennisSessionForm(
            user=self.user,
            data={
                "recording_mode": "live",
                "date": timezone.localdate().isoformat(),
                "session_type": "match",
                "focus": "Live match",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        session = form.save()

        self.assertTrue(session.is_in_progress)
        self.assertEqual(
            session.match_result,
            TennisSession.MatchResult.UNFINISHED,
        )
        self.assertEqual(form.cleaned_data["set_count"], 0)

    def test_completed_entry_records_manual_duration(self):
        local_start = timezone.localtime(self.started)

        form = GymWorkoutForm(data={
            "recording_mode": "completed",
            "date": local_start.date().isoformat(),
            "start_time": local_start.strftime("%H:%M"),
            "duration_minutes": 60,
            "title": "Earlier workout",
        })
        form.instance.user = self.user

        self.assertTrue(form.is_valid(), form.errors)
        session = form.save()

        self.assertFalse(session.is_in_progress)
        self.assertEqual(session.elapsed_seconds, 3600)

    def test_finish_now_for_both_session_types(self):
        for model, finish_name, _ in self.cases:
            with self.subTest(model=model.__name__):
                session = self.create_session(model)
                before = timezone.now()

                response = self.client.post(
                    reverse(f"tracking:{finish_name}", args=[session.pk]),
                    {"finish_mode": "now"},
                )

                self.assertEqual(response.status_code, 302)
                session.refresh_from_db()

                self.assertEqual(session.status, "completed")
                self.assertGreaterEqual(session.finished_at, before)
                self.assertLessEqual(
                    session.finished_at,
                    timezone.now(),
                )

    def test_custom_finish_can_cross_midnight(self):
        local_today = timezone.localtime(self.now).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        started = local_today - timedelta(days=1, minutes=30)
        finished = local_today - timedelta(days=1) + timedelta(
            minutes=30
        )

        for model, finish_name, _ in self.cases:
            with self.subTest(model=model.__name__):
                session = self.create_session(model)
                session.started_at = started
                session.date = started.date()
                session.save()

                response = self.client.post(
                    reverse(f"tracking:{finish_name}", args=[session.pk]),
                    {
                        "finish_mode": "custom",
                        "finished_at": self.local_input(finished),
                    },
                )

                self.assertEqual(response.status_code, 302)
                session.refresh_from_db()

                self.assertEqual(session.finished_at, finished)
                self.assertEqual(session.elapsed_seconds, 3600)

    def test_invalid_finish_times_do_not_complete_session(self):
        invalid_times = [
            self.started - timedelta(minutes=1),
            self.now + timedelta(days=1),
        ]

        for model, finish_name, _ in self.cases:
            for invalid_time in invalid_times:
                with self.subTest(
                    model=model.__name__,
                    finish=invalid_time,
                ):
                    session = self.create_session(model)

                    response = self.client.post(
                        reverse(
                            f"tracking:{finish_name}",
                            args=[session.pk],
                        ),
                        {
                            "finish_mode": "custom",
                            "finished_at": self.local_input(invalid_time),
                        },
                    )

                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.context["form"].errors)

                    session.refresh_from_db()
                    self.assertTrue(session.is_in_progress)
                    self.assertIsNone(session.finished_at)

    def test_old_completed_sessions_can_receive_duration(self):
        for model, _, times_name in self.cases:
            with self.subTest(model=model.__name__):
                session = self.create_session(model, active=False)
                self.assertIsNone(session.elapsed_seconds)

                response = self.client.post(
                    reverse(f"tracking:{times_name}", args=[session.pk]),
                    {
                        "started_at": self.local_input(self.started),
                        "duration_minutes": 90,
                    },
                )

                self.assertEqual(response.status_code, 302)
                session.refresh_from_db()

                self.assertEqual(session.status, "completed")
                self.assertEqual(session.elapsed_seconds, 5400)
                self.assertEqual(
                    session.date,
                    timezone.localtime(self.started).date(),
                )

    def test_other_user_cannot_finish_or_change_times(self):
        self.client.force_login(self.other_user)

        for model, finish_name, times_name in self.cases:
            session = self.create_session(model)

            for name in (finish_name, times_name):
                with self.subTest(model=model.__name__, route=name):
                    url = reverse(
                        f"tracking:{name}",
                        args=[session.pk],
                    )

                    self.assertEqual(
                        self.client.get(url).status_code,
                        404,
                    )
                    self.assertEqual(
                        self.client.post(
                            url,
                            {
                                "finish_mode": "now",
                                "started_at": self.local_input(
                                    self.started
                                ),
                                "duration_minutes": 60,
                            },
                        ).status_code,
                        404,
                    )

            session.refresh_from_db()
            self.assertTrue(session.is_in_progress)
            self.assertIsNone(session.finished_at)