from django.db import models

# Create your models here.
class ClientUser(models.Model):
    status_choices = [ 
        ('active','active'),
        ('inactive','inactive')
    ]
    user_id = models.BigIntegerField(unique=True)  # just store the ID of the user,without fk 
    # bcs the user is on the public , unique : no clientUser with multiple users 
    status = models.CharField(max_length=20 , choices=status_choices, default='active')
    role = models.CharField(max_length=50) # here must have defined values 


# method that retrieves the actual User instance 
# using the stored user_id 
    def get_user(self):
        from users.models import User
        try:
            return User.objects.get(id=self.user_id)
        except User.DoesNotExist:
            return None
        

        