from django.contrib import admin

from .models import Exercise


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "operand_a",
        "operand_b",
        "level",
        "is_active",
    )
    list_filter = ("is_active",)

    @admin.display(description="Nivel")
    def level(self, obj):
        return "Con llevadas" if obj.has_carry else "Sin llevadas"
