# users/models.py
from django.db import models

from django.contrib.auth.models import AbstractUser
from tenants.models import Client
from django.contrib.auth.base_user import BaseUserManager
from django.dispatch import receiver 
from django.urls import reverse 
from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import send_mail
from django.conf import settings

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None  # Remove the default username field
    email = models.EmailField(unique=True) 
    role = models.CharField(
        max_length=20, 
        choices=[('admin', 'admin'), ('Client', 'client'), ('userClient', 'userClient')],  # the user roles
        default='admin'
    )
    telephone = models.CharField(max_length=20, blank=True, null=True)
    logged_in = models.CharField(max_length=20, blank=True, null=True)
    logged_out = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'  # using the email on the authentication
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()



class Admin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    role = models.CharField(max_length=50)
    status_choices = [ 
        ('active','active'),
        ('inactive','inactive')
    ]
    status = models.CharField(max_length=20, blank=True, null=True, choices=status_choices, default='active') 





@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    email_plaintext_message = f"http://127.0.0.1:8000/api/user/reset-password?token={reset_password_token.key}"

    send_mail(
        subject="Password Reset for Your Account",
        message=email_plaintext_message,
        from_email='M-IOT <maamarmira005@gmail.com>' ,
        recipient_list=[reset_password_token.user.email],
        fail_silently=False,
    )