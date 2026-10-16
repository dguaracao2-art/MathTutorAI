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
