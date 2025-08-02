# maintenance/models.py
from django.db import models

class MaintenanceClient(models.Model):
    machine       = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    date_intervention = models.DateField()
    type          = models.CharField(max_length=50)
    resume        = models.TextField()
    file          = models.FileField(upload_to='maintenance_client/', blank=True, null=True)

class MaintenanceClientPredictive(models.Model):
    machine       = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    date_intervention = models.DateField()
    detail        = models.TextField()

class MaintenanceAdmin(models.Model):
    capture_machine = models.ForeignKey('machines.CaptureMachine', on_delete=models.CASCADE)
    date_intervention = models.DateField()
    type          = models.CharField(max_length=50)
    resume        = models.TextField()

class MaintenanceAdminPredictive(models.Model):
    capture_machine = models.ForeignKey('machines.CaptureMachine', on_delete=models.CASCADE)
    date_intervention = models.DateField()
    detail        = models.TextField()

class MaintenanceSensor(models.Model):
    maintenance   = models.ForeignKey(MaintenanceClient, on_delete=models.CASCADE)
    machine       = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    # composite primary key not directly supported; use unique_together:
    class Meta:
        unique_together = ('maintenance', 'machine')

class Attachment(models.Model):
    maintenance = models.ForeignKey(MaintenanceClient, on_delete=models.CASCADE, related_name='attachments')
    file_name   = models.CharField(max_length=255)
    file_path   = models.TextField()
