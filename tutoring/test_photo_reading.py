"""Regresión del flujo foto -> propuesta -> confirmación, sin descargar modelos."""
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
import time

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Exercise
from .services.handwriting import (
    CAMPOS, ReaderBusy, ReaderUnavailable, leer_fotografia, normalizar_lecturas,
)


def image_bytes(color='white'):
    stream = BytesIO()
    Image.new('RGB', (100, 100), color).save(stream, 'PNG')
    return stream.getvalue()


def proposal(a=23, b=14, result=32):
    values = dict(zip(CAMPOS, (a, b, result)))
    return {
        'estado': 'pendiente_de_confirmacion' if None not in values.values() else 'lectura_pendiente',
        'source': 'trocr-small-handwritten', 'propuesta': values,
        'can_confirm': any(v is not None for v in values.values()),
        'mensaje': 'Revisa los números de tu fotografía.',
    }


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PhotoReadingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='lector', password='prueba-local')
        cls.exercise = Exercise.objects.create(operand_a=23, operand_b=14)
        cls.other = Exercise.objects.create(operand_a=28, operand_b=17)

    def setUp(self):
        self.image = image_bytes()
        self.client.force_login(self.user)
        self.client.post(reverse('tutoring:select_exercise', args=[self.exercise.pk]))
        self.reader_patch = patch('tutoring.views.leer_fotografia', return_value=proposal())
        self.reader = self.reader_patch.start()
        self.addCleanup(self.reader_patch.stop)

    def photo(self, content=None):
        return SimpleUploadedFile('suma.png', self.image if content is None else content,
                                  content_type='image/png')

    def upload(self, client=None, **changes):
        data = {'exercise_id': str(self.exercise.pk), 'photo': self.photo()}
        data.update(changes)
        return (client or self.client).post(reverse('tutoring:upload_photo'), data)

    def confirm(self, token, client=None, **changes):
        data = {'exercise_id': str(self.exercise.pk), 'photo': self.photo(),
                'reading_token': token, 'operand_a': 23, 'operand_b': 14, 'written_result': 32}
        data.update(changes)
        return (client or self.client).post(reverse('tutoring:confirm_sum'), data)

    def test_upload_proposes_wrong_written_result_without_correcting_it(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['reading']['propuesta'], proposal()['propuesta'])
        self.assertTrue(response.json()['reading_token'])
        self.assertNotIn('confirmed_sum', self.client.session)
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_confirmation_preserves_32_and_records_origin(self):
        token = self.upload().json()['reading_token']
        response = self.confirm(token)
        self.assertEqual(response.status_code, 200)
        value = self.client.session['confirmed_sum']
        self.assertEqual(value['written_result'], 32)
        self.assertEqual(value['source'], 'ocr_confirmed')
        self.assertNotIn('correct', value)

    def test_human_can_correct_misread_operand(self):
        self.reader.return_value = proposal(b=15)
        response = self.confirm(self.upload().json()['reading_token'])
        self.assertEqual(response.status_code, 200)
        value = response.json()['confirmed']
        self.assertEqual(value['operand_b'], 14)
        self.assertEqual(value['original_proposal']['operand_b'], 15)
        self.assertEqual(value['source'], 'ocr_edited')

    def test_partial_reading_leaves_null_and_allows_completion(self):
        self.reader.return_value = proposal(b=None)
        response = self.upload()
        self.assertIsNone(response.json()['reading']['propuesta']['operand_b'])
        self.assertEqual(self.confirm(response.json()['reading_token']).status_code, 200)

    def test_zero_is_valid(self):
        exercise = Exercise.objects.create(operand_a=0, operand_b=0)
        self.client.post(reverse('tutoring:select_exercise', args=[exercise.pk]))
        self.reader.return_value = proposal(0, 0, 0)
        response = self.upload(exercise_id=str(exercise.pk))
        response = self.confirm(response.json()['reading_token'], exercise_id=str(exercise.pk),
                                operand_a=0, operand_b=0, written_result=0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['confirmed']['written_result'], 0)

    def test_unreadable_geometry_has_no_confirmation_token(self):
        self.reader.return_value = proposal(None, None, None)
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['reading']['can_confirm'])
        self.assertEqual(response.json()['reading_token'], '')

    def test_blank_image_is_rejected_before_model(self):
        self.reader.side_effect = leer_fotografia
        with patch('tutoring.services.handwriting.reconocer_recortes') as model:
            response = self.upload()
        model.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['reading']['can_confirm'])

    def test_other_photo_cannot_use_previous_reading(self):
        token = self.upload().json()['reading_token']
        self.assertEqual(self.confirm(token, photo=self.photo(image_bytes('black'))).status_code, 409)
        self.assertNotIn('confirmed_sum', self.client.session)

    def test_missing_or_tampered_token(self):
        token = self.upload().json()['reading_token']
        for invalid in ('', token + 'x'):
            with self.subTest(token=invalid[:6]):
                self.assertEqual(self.confirm(invalid).status_code, 409)

    def test_expired_token_requests_reload(self):
        token = self.upload().json()['reading_token']
        with patch('django.core.signing.time.time', return_value=time.time() + 1900):
            self.assertEqual(self.confirm(token).status_code, 409)

    def test_token_cannot_move_to_another_session(self):
        token = self.upload().json()['reading_token']
        other_client = Client()
        other_client.force_login(self.user)
        other_client.post(reverse('tutoring:select_exercise', args=[self.exercise.pk]))
        self.assertEqual(self.confirm(token, client=other_client).status_code, 409)

    def test_operands_must_match_selected_exercise(self):
        token = self.upload().json()['reading_token']
        response = self.confirm(token, operand_b=15)
        self.assertEqual(response.status_code, 400)
        self.assertIn('No coincide', response.json()['error'])

    def test_invalid_numbers_are_not_confirmed(self):
        token = self.upload().json()['reading_token']
        for field, value in [('operand_a', -1), ('operand_b', 1000),
                             ('written_result', 10000), ('written_result', '3.2')]:
            with self.subTest(field=field, value=value):
                self.assertEqual(self.confirm(token, **{field: value}).status_code, 400)

    def test_anonymous_requests_do_not_run_ocr(self):
        self.client.logout()
        self.assertEqual(self.upload().status_code, 401)
        self.assertEqual(self.confirm('').status_code, 401)
        self.reader.assert_not_called()

    def test_missing_selection_does_not_run_ocr(self):
        session = self.client.session
        session.pop('selected_exercise')
        session.save()
        self.assertEqual(self.upload().status_code, 409)
        self.reader.assert_not_called()

    def test_different_or_inactive_exercise_does_not_run_ocr(self):
        self.assertEqual(self.upload(exercise_id=str(self.other.pk)).status_code, 409)
        Exercise.objects.filter(pk=self.exercise.pk).update(is_active=False)
        self.assertEqual(self.upload().status_code, 409)
        self.reader.assert_not_called()

    def test_changed_operands_do_not_run_ocr(self):
        Exercise.objects.filter(pk=self.exercise.pk).update(operand_b=15)
        self.assertEqual(self.upload().status_code, 409)
        self.reader.assert_not_called()

    def test_invalid_or_large_file_does_not_run_ocr(self):
        for content in (b'no es una foto', self.image + b'\0' * (5 * 1024 * 1024)):
            self.assertEqual(self.upload(photo=self.photo(content)).status_code, 400)
        self.reader.assert_not_called()

    def test_new_upload_invalidates_previous_confirmation_before_ocr(self):
        token = self.upload().json()['reading_token']
        self.confirm(token)
        def inspect(*args):
            self.assertNotIn('confirmed_sum', self.client.session)
            return proposal()
        self.reader.side_effect = inspect
        self.assertEqual(self.upload().status_code, 200)
        self.assertNotIn('confirmed_sum', self.client.session)

    def test_selection_changed_during_ocr_is_preserved(self):
        def change_selection(*args):
            session = self.client.session
            session['selected_exercise'] = {'id': self.other.pk, 'operand_a': 28, 'operand_b': 17}
            session.save()
            return proposal()
        self.reader.side_effect = change_selection
        self.assertEqual(self.upload().status_code, 409)
        self.assertEqual(self.client.session['selected_exercise']['id'], self.other.pk)

    def test_logout_during_ocr_does_not_recreate_session(self):
        key = self.client.session.session_key
        def logout(*args):
            Session.objects.filter(session_key=key).delete()
            return proposal()
        self.reader.side_effect = logout
        self.assertEqual(self.upload().status_code, 401)
        self.assertFalse(Session.objects.filter(session_key=key).exists())

    def test_disabled_during_ocr_is_not_confirmable(self):
        def deactivate(*args):
            Exercise.objects.filter(pk=self.exercise.pk).update(is_active=False)
            return proposal()
        self.reader.side_effect = deactivate
        self.assertEqual(self.upload().status_code, 409)

    def test_busy_and_unavailable_produce_json_errors(self):
        self.reader.side_effect = ReaderBusy('Espera un momento.')
        self.assertEqual(self.upload().status_code, 429)
        self.reader.side_effect = ReaderUnavailable('Error de prueba')
        with self.assertLogs('tutoring.views', level='ERROR'):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertIn('error', response.json())

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(self.upload(client=client).status_code, 403)
        self.assertEqual(self.confirm('', client=client).status_code, 403)
        self.reader.assert_not_called()

    def test_get_is_not_allowed_for_mutations(self):
        for name in ('upload_photo', 'confirm_sum'):
            self.assertEqual(self.client.get(reverse('tutoring:' + name)).status_code, 405)

    def test_template_exposes_token_and_editable_fields(self):
        response = self.client.get(reverse('tutoring:exercise_detail'))
        self.assertContains(response, 'name="reading_token"')
        self.assertContains(response, 'Cargar y leer fotografía')
        for name in CAMPOS:
            self.assertContains(response, f'name="{name}"')


class NormalizationTests(SimpleTestCase):
    def test_spaces_and_zero_are_read_without_arithmetic(self):
        self.assertEqual(normalizar_lecturas(dict(zip(CAMPOS, ('2 3', '0', '3 2')))),
                         dict(zip(CAMPOS, (23, 0, 32))))

    def test_ambiguous_characters_are_not_silently_removed(self):
        for text in ('1O', '14"', '-1', '3.2', '', '١٤', '10000'):
            with self.subTest(text=text):
                self.assertIsNone(normalizar_lecturas(dict.fromkeys(CAMPOS, text))['written_result'])

    def test_operand_and_result_limits_differ(self):
        values = normalizar_lecturas(dict.fromkeys(CAMPOS, '1000'))
        self.assertIsNone(values['operand_a'])
        self.assertIsNone(values['operand_b'])
        self.assertEqual(values['written_result'], 1000)
