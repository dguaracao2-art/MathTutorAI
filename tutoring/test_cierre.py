"""Regresión de llevadas confirmadas, JPEG de cámara y diagnóstico del lector."""
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .forms import PhotoUploadForm
from .models import Attempt, Exercise
from .services.handwriting import ReaderUnavailable, leer_fotografia, preparar_suma
from .services.hints import hints_for
from .services.sum_review import review_sum


class ConfirmedCarryTests(SimpleTestCase):
    def test_wrong_visible_mark_is_reviewed_even_with_correct_result(self):
        review = review_sum(28, 17, 45, carries={'decenas': 0})
        self.assertEqual((review['status'], review['column_name'], review['mismatch_kind']),
                         ('requiere_revision', 'decenas', 'carry'))
        self.assertEqual(sum(c['carry_needs_review'] for c in review['columns']), 1)
        self.assertFalse(any(c['result_needs_review'] for c in review['columns']))
        self.assertEqual(len(hints_for(review)), 2)
        self.assertNotIn('45', ' '.join(hints_for(review)))

    def test_chain_of_confirmed_carries(self):
        review = review_sum(999, 1, 1000, carries={
            'decenas': 1, 'centenas': 1, 'unidades de millar': 1,
        })
        self.assertEqual((review['status'], review['carry_count']), ('correcto', 3))

    def test_absent_marks_are_not_assumed_to_be_wrong(self):
        self.assertEqual(review_sum(28, 17, 45)['carry_count'], 0)
        self.assertEqual(review_sum(28, 17, 45, carries={'centenas': 0})['status'], 'correcto')

    def test_first_discrepancy_is_selected_from_right_to_left(self):
        review = review_sum(28, 17, 44, carries={'decenas': 0})
        self.assertEqual((review['column_name'], review['mismatch_kind']), ('unidades', 'result'))
        review = review_sum(23, 14, 137, carries={'decenas': 1})
        self.assertEqual((review['column_name'], review['mismatch_kind']), ('decenas', 'carry'))

    def test_invalid_marks_are_rejected(self):
        for marks in ({'decenas': 2}, {'decenas': True}, {'unidades': 1}, [], {'decenas': None}):
            with self.subTest(marks=marks), self.assertRaises(ValueError):
                review_sum(28, 17, 45, carries=marks)

    def test_geometry_with_no_recognized_numbers_allows_manual_confirmation(self):
        reading = {'propuesta': dict.fromkeys(('operand_a', 'operand_b', 'written_result')),
                   'estado': 'lectura_pendiente', 'source': 'lector-prueba',
                   'lecturas_crudas': {'operand_a': 'x', 'operand_b': '', 'written_result': ''}}
        with patch('tutoring.services.handwriting.preparar_suma', return_value=(None, None, [], {}, None)), \
                patch('tutoring.services.handwriting.reconocer_recortes', return_value=reading):
            result = leer_fotografia(BytesIO())
        self.assertTrue(result['can_confirm'])
        self.assertEqual(result['estado'], 'lectura_pendiente')
        self.assertEqual(result['etapa'], 'reconocimiento')
        self.assertNotIn('lecturas_crudas', result)

    def test_model_failure_does_not_masquerade_as_manual_reading(self):
        with patch('tutoring.services.handwriting.preparar_suma', return_value=(None, None, [], {}, None)), \
                patch('tutoring.services.handwriting.reconocer_recortes', side_effect=ReaderUnavailable('sin modelo')):
            with self.assertRaises(ReaderUnavailable):
                leer_fotografia(BytesIO())

    def test_camera_jpeg_with_auxiliary_mpo_frame_uses_primary_photo(self):
        stream = BytesIO()
        Image.new('RGB', (64, 48), 'blue').save(
            stream, 'MPO', save_all=True, append_images=[Image.new('RGB', (16, 16), 'black')])
        data = stream.getvalue()
        form = PhotoUploadForm(files={'photo': SimpleUploadedFile('camara.jpeg', data)})
        self.assertTrue(form.is_valid(), form.errors)
        seen = []

        def stop_at_segmentation(image, *args, **kwargs):
            seen.append(image.size)
            from .services.handwriting import PhotoNotReadable
            raise PhotoNotReadable('solo se prueba la apertura')

        from .services.handwriting import PhotoNotReadable
        with patch('tutoring.services.handwriting._separar_suma', side_effect=stop_at_segmentation):
            with self.assertRaises(PhotoNotReadable):
                preparar_suma(BytesIO(data))
        self.assertEqual(set(seen), {(64, 48)})


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CarryWebFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='llevadas', password='solo-prueba')
        cls.exercise = Exercise.objects.create(operand_a=28, operand_b=17)

    def setUp(self):
        self.client.force_login(self.user)
        self.client.post(reverse('tutoring:select_exercise', args=[self.exercise.pk]))
        reader = patch('tutoring.views.leer_fotografia', return_value={
            'estado': 'pendiente_de_confirmacion', 'source': 'lector-prueba', 'can_confirm': True,
            'propuesta': {'operand_a': 28, 'operand_b': 17, 'written_result': 45}, 'mensaje': '',
        })
        self.reader = reader.start()
        self.addCleanup(reader.stop)

    def photo(self):
        stream = BytesIO()
        Image.new('RGB', (40, 40), 'white').save(stream, 'PNG')
        return SimpleUploadedFile('suma.png', stream.getvalue(), content_type='image/png')

    def confirm(self, **marks):
        token = self.client.post(reverse('tutoring:upload_photo'), {
            'exercise_id': self.exercise.pk, 'photo': self.photo(),
        }).json()['reading_token']
        return self.client.post(reverse('tutoring:confirm_sum'), {
            'exercise_id': self.exercise.pk, 'photo': self.photo(), 'reading_token': token,
            'operand_a': 28, 'operand_b': 17, 'written_result': 45, **marks,
        })

    def test_confirmed_mark_is_checked_and_persisted_without_photo(self):
        response = self.confirm(carry_tens=0)
        self.assertEqual(response.status_code, 200)
        confirmed = response.json()['confirmed']
        self.client.post(reverse('tutoring:check_sum'), {
            'exercise_id': self.exercise.pk, 'confirmation_id': confirmed['confirmation_id'],
        })
        attempt = Attempt.objects.get()
        self.assertEqual((attempt.carries, attempt.status), ({'decenas': 0}, 'requiere_revision'))
        self.assertNotIn('photo', [field.name for field in Attempt._meta.fields])
        page = self.client.get(reverse('tutoring:review_result'))
        self.assertContains(page, 'marca')
        self.assertContains(page, 'Llevadas')

    def test_invalid_mark_is_not_confirmed(self):
        for value in (-1, 2, '1.5'):
            with self.subTest(value=value):
                self.assertEqual(self.confirm(carry_tens=value).status_code, 400)
        self.assertFalse(Attempt.objects.exists())

    def test_manual_completion_is_identified_without_changing_ocr_proposal(self):
        self.reader.return_value['propuesta'] = dict.fromkeys(
            ('operand_a', 'operand_b', 'written_result'))
        self.reader.return_value['estado'] = 'lectura_pendiente'
        confirmed = self.confirm().json()['confirmed']
        self.assertEqual(confirmed['source'], 'manual_confirmed')
        self.assertTrue(all(value is None for value in confirmed['original_proposal'].values()))
        self.assertEqual(confirmed['written_result'], 45)

    def test_blank_mark_stays_absent_and_form_offers_all_columns(self):
        confirmed = self.confirm().json()['confirmed']
        self.assertEqual(confirmed['carries'], {})
        self.assertIsNone(confirmed['carry_tens'])
        page = self.client.get(reverse('tutoring:exercise_detail'))
        for name in ('carry_tens', 'carry_hundreds', 'carry_thousands'):
            self.assertContains(page, f'name="{name}"')
