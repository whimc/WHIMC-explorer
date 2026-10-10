from django import forms
from explorer_core.scoring import label


class StudyLabelsForm(forms.Form):
    study = forms.CharField(max_length=128, required=False, label='Study', help_text='Example: Fall 2026 Habitat Study')
    location = forms.CharField(max_length=128, required=False, label='Study location', help_text='Example: Lincoln School')
    session_name = forms.CharField(max_length=128, required=False, label='Session name', help_text='Example: Week 3 — Mars habitat building')

    def clean(self):
        result = super().clean()
        for key, value in result.items():
            if value:
                try:
                    label(value)
                except ValueError as exc:
                    self.add_error(key, str(exc))
        return result
