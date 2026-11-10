"""Validación de la API. Reutiliza los límites ya definidos para la web.

No se duplican reglas: la fotografía pasa por el mismo formulario que usa la
página y los números conservan el alcance de la práctica.
"""
from rest_framework import serializers

from .forms import PhotoUploadForm
from .services.sum_review import COLUMN_NAMES

COLUMNAS_CON_MARCA = COLUMN_NAMES[1:]


class LecturaSerializer(serializers.Serializer):
    """Entrada de M2: la fotografía de la hoja."""

    fotografia = serializers.ImageField()

    def validate_fotografia(self, archivo):
        formulario = PhotoUploadForm(files={'photo': archivo})
        if not formulario.is_valid():
            raise serializers.ValidationError(formulario.errors['photo'])
        return formulario.cleaned_data['photo']


class RevisionSerializer(serializers.Serializer):
    """Entrada de M3: los números que el estudiante ya confirmó.

    La comprobación nunca parte de una lectura automática sin confirmar.
    """

    operand_a = serializers.IntegerField(min_value=0, max_value=999)
    operand_b = serializers.IntegerField(min_value=0, max_value=999)
    written_result = serializers.IntegerField(min_value=0, max_value=9999)
    carries = serializers.DictField(
        child=serializers.IntegerField(min_value=0, max_value=1),
        required=False, allow_empty=True,
        help_text='Marcas de llevada transcritas a mano, por ejemplo {"decenas": 1}.',
    )

    def validate_carries(self, marcas):
        desconocidas = sorted(set(marcas) - set(COLUMNAS_CON_MARCA))
        if desconocidas:
            raise serializers.ValidationError(
                f'Columnas no admitidas: {", ".join(desconocidas)}. '
                f'Usa {", ".join(COLUMNAS_CON_MARCA)}.')
        return marcas


class PistaSerializer(RevisionSerializer):
    """Entrada de M4: los mismos números y cuál de las dos pistas se pide."""

    numero = serializers.IntegerField(min_value=1, max_value=2)
