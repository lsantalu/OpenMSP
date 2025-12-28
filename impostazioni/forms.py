from django import forms
from django.contrib.auth.models import User

class CloneUserForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Ripeti password", widget=forms.PasswordInput)
    is_active = forms.BooleanField(label="Utente attivo", required=False, initial=True)
    is_superuser = forms.BooleanField(label="Utente amministratore", required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'is_active', 'is_superuser']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Le password non coincidono.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
