# tenants/models.py
from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
from django.conf import settings

class Client(TenantMixin): # inherit from 
    # ID is automatically primary key
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='client_account'
    )
    nom_entreprise = models.CharField(max_length=100, unique=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    industrie = models.CharField(max_length=100, blank=True, null=True)
    nom_resp = models.CharField(max_length=50, blank=True, null=True)
    prenom_resp = models.CharField(max_length=50, blank=True, null=True)
    status_choices = [ 
        ('active','active'),
        ('inactive','inactive')
    ]
    status = models.CharField(max_length=50, blank=True, null=True, choices=status_choices, default='active')

    auto_create_schema = True  # required for django-tenants


class Domain(DomainMixin):
    pass # because all the rest django will hendle 