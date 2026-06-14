from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthTests(TestCase):
    def test_register_creates_user_and_logs_in(self):
        resp = self.client.post(reverse("register"), {
            "username": "carol",
            "email": "carol@example.com",
            "full_name": "Carol Smith",
            "password1": "Str0ngPass!23",
            "password2": "Str0ngPass!23",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(username="carol").exists())
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_login_logout(self):
        User.objects.create_user("dave", "dave@example.com", "pw12345!")
        self.assertTrue(self.client.login(username="dave", password="pw12345!"))
        resp = self.client.post(reverse("logout"))
        self.assertEqual(resp.status_code, 302)

    def test_profile_requires_login(self):
        resp = self.client.get(reverse("profile"))
        self.assertEqual(resp.status_code, 302)

    def test_profile_update(self):
        user = User.objects.create_user("erin", "erin@example.com", "pw12345!")
        self.client.force_login(user)
        resp = self.client.post(reverse("profile"), {
            "username": "erin", "email": "erin@new.com", "full_name": "Erin New",
        })
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.email, "erin@new.com")
        self.assertEqual(user.full_name, "Erin New")
