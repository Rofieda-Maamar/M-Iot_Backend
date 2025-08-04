# reports/models.py
from django.db import models

class RapportPlanification(models.Model):
    site             = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='reports')
    nom_rapport      = models.CharField(max_length=100)
    destinataire     = models.CharField(max_length=255)
    email_dest       = models.EmailField()
    type_rapport     = models.CharField(max_length=50)
    periodicite      = models.DecimalField(max_digits=10, decimal_places=2)
    date_dernier_envoi = models.DateField()
    heur_envoi       = models.TimeField()
    status             = models.CharField(max_length=20)

 

class RapportHistoriqueMesure(models.Model):
    rapport_plan    = models.ForeignKey(RapportPlanification, on_delete=models.CASCADE, related_name='historiques')
    machine         = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    date_debut      = models.DateField()
    date_fin        = models.DateField()
    heur_debut      = models.TimeField()
    heur_fin        = models.TimeField()
    frequence       = models.DecimalField(max_digits=10, decimal_places=2)

class RapportAnalyseGraphique(models.Model):
    rapport_plan    = models.ForeignKey(RapportPlanification, on_delete=models.CASCADE, related_name='analyses')
    machine         = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    capture_site    = models.ForeignKey('captures.CaptureSite', on_delete=models.CASCADE)
    date            = models.DateField()
    heur_debut      = models.TimeField()
    heur_fin        = models.TimeField()

class RapportJournalier(models.Model):
    rapport_plan    = models.ForeignKey(RapportPlanification, on_delete=models.CASCADE, related_name='journaliers')
    machine         = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    parametre       = models.ForeignKey('captures.TypeParametre', on_delete=models.CASCADE)
    date_debut      = models.DateField()
    date_fin        = models.DateField()
    horaire_matin   = models.TimeField()
    horaire_midi    = models.TimeField()
    horaire_soire   = models.TimeField()

class LogRapport(models.Model):
    rapport_plan    = models.ForeignKey(RapportPlanification, on_delete=models.CASCADE, related_name='logs')
    date_envoi      = models.DateField()
    heure_envoi     = models.TimeField()
    etat_envoi      = models.CharField(max_length=20)
