# maintenance/models.py
from django.db import models

from users.models import  Admin
from machines.models import Machine 
from machines.models import CaptureMachine
from ClientUsers.models import ClientUser

class MaintenanceClient(models.Model):
    client = models.ForeignKey('ClientUsers.ClientUser', on_delete=models.CASCADE)
    machine = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    date_intervention = models.DateField()
    type = models.CharField(max_length=50)
    resume = models.TextField()

class MaintenanceClientPredictive(models.Model):
    client = models.ForeignKey('ClientUsers.ClientUser', on_delete=models.CASCADE)
    machine = models.ForeignKey('machines.Machine', on_delete=models.CASCADE)
    date_intervention = models.DateField()
    detail = models.TextField()

class MaintenanceAdmin(models.Model):
   
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, related_name="maintenance_maintenanceprd_admins")
    capture_machine = models.ForeignKey('machines.CaptureMachine', on_delete=models.CASCADE)
    date_intervention = models.DateField()
    type = models.CharField(max_length=50)
    resume = models.TextField()

class MaintenanceAdminPredictive(models.Model):
    admin = models.ForeignKey('users.Admin', on_delete=models.CASCADE)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, related_name="maintenance_maintenanceprd_admins")
    capture_machine = models.ForeignKey('machines.CaptureMachine', on_delete=models.CASCADE)
    
    date_intervention = models.DateField()
    detail = models.TextField()

class FichierMaintenanceAdmin(models.Model):
    maintenance = models.ForeignKey(MaintenanceAdmin, on_delete=models.CASCADE)
    url = models.CharField(max_length=255)


class FichierMaintenanceClient(models.Model):
    maintenance = models.ForeignKey(MaintenanceClient, on_delete=models.CASCADE)
    url = models.CharField(max_length=255)
