from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class StudentRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["autocomplete"] = (
                "username" if name == "username" else "new-password"
            )
