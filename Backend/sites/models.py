from django.db import models

class Site(models.Model):
    nom            = models.CharField(max_length=100)
    adresse        = models.CharField(max_length=255, blank=True, null=True)
    latitude       = models.FloatField(blank=True, null=True)
    longitude      = models.FloatField(blank=True, null=True)
    asset_tracking = models.BooleanField(default=False)
    etat           = models.CharField(max_length=20)
    date_ajout     = models.DateTimeField(auto_now_add=True)

