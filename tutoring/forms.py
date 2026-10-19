from django import forms
from PIL import Image


class PhotoUploadForm(forms.Form):
    photo = forms.ImageField(
        error_messages={
            "required": "Selecciona una fotografía.",
            "invalid_image": (
                "El archivo no es una imagen válida. "
                "Selecciona JPG o PNG."
            ),
            "invalid_extension": "Selecciona una imagen JPG o PNG.",
            "empty": "El archivo está vacío.",
        }
    )

    def clean_photo(self):
        photo = self.cleaned_data["photo"]

        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "La fotografía debe pesar como máximo 5 MB."
            )

        if photo.image.format not in ("JPEG", "PNG"):
            raise forms.ValidationError(
                "Selecciona una imagen JPG o PNG."
            )

        if photo.image.width * photo.image.height > 20_000_000:
            raise forms.ValidationError(
                "Usa una fotografía de hasta 20 megapíxeles."
            )

        try:
            photo.seek(0)
            with Image.open(photo) as image:
                image.load()
        except (OSError, ValueError, SyntaxError):
            raise forms.ValidationError(
                "La imagen está dañada. Selecciona otra fotografía."
            )
        finally:
            photo.seek(0)

        return photo