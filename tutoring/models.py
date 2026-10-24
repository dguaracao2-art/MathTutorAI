from django.core.validators import MaxValueValidator
from django.db import models


class Exercise(models.Model):
    operand_a = models.PositiveSmallIntegerField(
        "Primer número",
        validators=[MaxValueValidator(999)],
    )
    operand_b = models.PositiveSmallIntegerField(
        "Segundo número",
        validators=[MaxValueValidator(999)],
    )
    is_active = models.BooleanField("Disponible", default=True)

    class Meta:
        verbose_name = "suma"
        verbose_name_plural = "sumas"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    operand_a__lte=999,
                    operand_b__lte=999,
                ),
                name="exercise_operands_max_999",
            ),
        ]

    @property
    def has_carry(self):
        a, b = self.operand_a, self.operand_b

        while a or b:
            if a % 10 + b % 10 >= 10:
                return True

            a //= 10
            b //= 10

        return False

    def __str__(self):
        return f"{self.operand_a} + {self.operand_b}"


class Attempt(models.Model):
    """Revisión confirmada. No almacena fotografías ni una respuesta inferida por OCR."""
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='sum_attempts')
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name='attempts')
    confirmation_id = models.CharField(max_length=32, unique=True)
    operand_a = models.PositiveSmallIntegerField()
    operand_b = models.PositiveSmallIntegerField()
    written_result = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=[
        ('correcto', 'Correcto'), ('corregido', 'Corregido'),
        ('requiere_revision', 'Requiere revisión'),
    ])
    hint_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.user_id}: {self.operand_a} + {self.operand_b} = {self.written_result}'
