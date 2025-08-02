# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    telephone    = models.CharField(max_length=20, blank=True, null=True)
    logged_in    = models.DateTimeField(blank=True, null=True)
    logged_out   = models.DateTimeField(blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)




class AdminProfile(models.Model):
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='admin_profile'
    )
    nom   = models.CharField(max_length=50)
    prenom= models.CharField(max_length=50)

    def __str__(self):
        return f"{self.nom} {self.prenom}"