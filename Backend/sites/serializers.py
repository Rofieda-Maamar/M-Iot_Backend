from .models import Site
from rest_framework import serializers



# for the client sites display
class SiteNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ['nom']