# users/models.py
from django.db import models

from django.contrib.auth.models import AbstractUser
from tenants.models import Client


class User(AbstractUser):
    telephone = models.CharField(max_length=20, blank=True, null=True)
    logged_in = models.CharField(max_length=20, blank=True, null=True)
    logged_out = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)

class Admin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    role = models.CharField(max_length=50)
    status = models.CharField(max_length=20, blank=True, null=True) 

class ClientUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    client = models.ForeignKey("tenants.Client", on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    role = models.CharField(max_length=50)