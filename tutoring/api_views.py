"""API REST de la práctica: expone M2, M3 y M4 sin duplicar sus reglas.

Las vistas web siguen funcionando igual. Esta interfaz reutiliza los mismos
servicios, conserva el alcance de sumas y mantiene las dos condiciones del
proyecto: la comprobación parte de números confirmados y no se ofrece una
tercera pista ni se revela el resultado.

Requiere sesión iniciada, como el resto de la práctica (RNF-03).
"""
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LecturaSerializer, PistaSerializer, RevisionSerializer
from .services.handwriting import ReaderBusy, ReaderUnavailable, leer_fotografia
from .services.hints import hints_for
from .services.sum_review import review_sum

MAXIMO_DE_PISTAS = 2


def _revisar(datos):
    """Aplicar las reglas aritméticas sobre los números confirmados."""
    return review_sum(
        datos['operand_a'], datos['operand_b'], datos['written_result'],
        carries=datos.get('carries') or {},
    )


class LecturaAPIView(APIView):
    """M2. Propone los tres números de una fotografía, sin comprobarlos."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        entrada = LecturaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            lectura = leer_fotografia(entrada.validated_data['fotografia'])
        except ReaderBusy:
            return Response(
                {'detail': 'El lector está atendiendo otra fotografía. '
                           'Espera un momento y vuelve a enviarla.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ReaderUnavailable:
            return Response(
                {'detail': 'El lector no está disponible en este servidor.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        # La propuesta es editable: el estudiante debe confirmarla antes de
        # pedir una comprobación, igual que en la página.
        lectura['confirmacion_requerida'] = True
        return Response(lectura)


class RevisionAPIView(APIView):
    """M3. Comprueba números ya confirmados y localiza la discrepancia."""

    def post(self, request):
        entrada = RevisionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        revision = _revisar(entrada.validated_data)
        correcto = revision['status'] == 'correcto'
        return Response({
            'estado': revision['status'],
            'columna': revision['column_name'],
            'columnas': revision['columns'],
            'tipo_de_discrepancia': revision['mismatch_kind'],
            'pistas_disponibles': 0 if correcto else MAXIMO_DE_PISTAS,
        })


class PistaAPIView(APIView):
    """M4. Entrega una sola pista del catálogo revisado, por número."""

    def post(self, request):
        entrada = PistaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        pistas = hints_for(_revisar(datos))
        if not pistas:
            return Response(
                {'detail': 'La suma confirmada no presenta discrepancias; '
                           'no corresponde una pista.'},
                status=status.HTTP_409_CONFLICT)
        # El catálogo tiene dos pasos por discrepancia; no hay un tercero.
        return Response({
            'numero': datos['numero'],
            'pista': pistas[datos['numero'] - 1],
            'pistas_disponibles': len(pistas),
        })
