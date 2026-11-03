from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse


class RegistrationTests(TestCase):
    def setUp(self):
        self.url = reverse("accounts:register")
        self.data = {"username": "estudiante", "password1": "Bosque!27Luna#93",
                     "password2": "Bosque!27Luna#93"}

    def test_registration_login_and_no_admin_privileges(self):
        response = self.client.post(self.url, {**self.data, "is_staff": "1",
            "is_superuser": "1", "groups": "1", "next": "https://example.org"})
        self.assertRedirects(response, reverse("accounts:login") + "?registered=1")
        user = get_user_model().objects.get(username="estudiante")
        self.assertTrue(user.check_password(self.data["password1"]))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.groups.exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(self.client.login(username=user.username, password=self.data["password1"]))
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")

    def test_invalid_passwords_and_username_do_not_create_users(self):
        for changes in ({"password2": "Otra"}, {"password1": "123", "password2": "123"},
                        {"username": "no valido"}, {"username": ""}):
            with self.subTest(changes=changes):
                response = self.client.post(self.url, {**self.data, **changes})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(get_user_model().objects.exists())

    def test_duplicate_username(self):
        get_user_model().objects.create_user(username="estudiante")
        response = self.client.post(self.url, self.data)
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_csrf_required(self):
        response = Client(enforce_csrf_checks=True).post(self.url, self.data)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.exists())

    def test_authenticated_user_redirected_without_creating_another(self):
        user = get_user_model().objects.create_user(username="existente")
        self.client.force_login(user)
        self.assertRedirects(self.client.post(self.url, self.data), reverse("accounts:home"))
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_navigation_and_password_not_echoed(self):
        self.assertContains(self.client.get(reverse("accounts:login")), self.url)
        response = self.client.post(self.url, {**self.data, "password2": "Otra"})
        self.assertNotContains(response, self.data["password1"])
        self.assertContains(response, 'autocomplete="new-password"')
