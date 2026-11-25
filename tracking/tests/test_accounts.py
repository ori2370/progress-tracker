from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AccountTests(TestCase):
    def setUp(self):
        self.password = "Original-Account-Pass-472!"
        self.user = get_user_model().objects.create_user(
            username="account-owner",
            email="owner@example.com",
            password=self.password,
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-owner",
            email="other@example.com",
        )

    def test_home_and_account_pages_require_login(self):
        for name in ("home", "profile", "password-change"):
            with self.subTest(page=name):
                url = reverse(f"tracking:{name}")
                response = self.client.get(url)

                self.assertRedirects(
                    response,
                    f"{reverse('tracking:login')}?next={url}",
                )

    def test_login_returns_to_home(self):
        response = self.client.post(
            reverse("tracking:login"),
            {
                "username": self.user.username,
                "password": self.password,
            },
        )

        self.assertRedirects(
            response,
            reverse("tracking:home"),
        )
        self.assertEqual(
            self.client.session["_auth_user_id"],
            str(self.user.pk),
        )

    def test_login_rejects_external_redirect(self):
        response = self.client.post(
            reverse("tracking:login"),
            {
                "username": self.user.username,
                "password": self.password,
                "next": "https://example.com/",
            },
        )

        self.assertRedirects(
            response,
            reverse("tracking:home"),
        )

    def test_profile_updates_only_current_user_and_returns_home(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("tracking:profile"),
            {
                "username": "updated-owner",
                "email": "updated@example.com",
                "first_name": "Ori",
                "last_name": "Example",
                "id": self.other_user.pk,
                "is_superuser": "true",
                "is_staff": "true",
            },
        )

        self.assertRedirects(
            response,
            reverse("tracking:home"),
        )

        self.user.refresh_from_db()
        self.other_user.refresh_from_db()

        self.assertEqual(self.user.username, "updated-owner")
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(self.user.first_name, "Ori")
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.other_user.username, "other-owner")
        self.assertEqual(self.other_user.email, "other@example.com")

    def test_duplicate_username_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("tracking:profile"),
            {
                "username": self.other_user.username,
                "email": self.user.email,
                "first_name": "",
                "last_name": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "account-owner")

    def test_password_change_requires_correct_current_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("tracking:password-change"),
            {
                "old_password": "incorrect-password",
                "new_password1": "Replacement-Password-893!",
                "new_password2": "Replacement-Password-893!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "old_password",
            response.context["form"].errors,
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_password_change_preserves_current_session(self):
        self.client.force_login(self.user)
        new_password = "Replacement-Password-893!"

        response = self.client.post(
            reverse("tracking:password-change"),
            {
                "old_password": self.password,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.assertRedirects(
            response,
            reverse("tracking:profile"),
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(self.password))

        response = self.client.get(reverse("tracking:home"))
        self.assertTrue(response.context["user"].is_authenticated)

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.user)
        url = reverse("tracking:logout")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse("tracking:login"),
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post(reverse("tracking:logout"))

        self.assertEqual(response.status_code, 403)
        self.assertIn("_auth_user_id", client.session)