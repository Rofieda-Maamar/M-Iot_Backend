from django.db import models

class Site(models.Model):
    etat_choices= [
        ('active','active'),
        ('inactive','inactive')
    ]
    nom            = models.CharField(max_length=100)
    adresse        = models.CharField(max_length=255, blank=True, null=True)
    latitude       = models.FloatField(blank=True, null=True)
    longitude      = models.FloatField(blank=True, null=True)
    asset_tracking = models.BooleanField(default=False)
<<<<<<< HEAD
    etat           = models.CharField(max_length=20)
    date_ajout     = models.DateTimeField(auto_now_add=True)
=======
    etat           = models.CharField(max_length=20 , choices=etat_choices , default='active')
    date_ajout     = models.DateTimeField(auto_now_add=True)

>>>>>>> Rofieda
