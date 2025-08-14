from django.shortcuts import render


from django.shortcuts import render
from rest_framework import generics , status
from sites.models import Site
import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
# Create your views here.
from .serializers import TagRfidSerializer 
from rest_framework import generics

class CreateTagRfidView (generics.CreateAPIView) : 
    serializer_class = TagRfidSerializer

    def perform_create(self, serializer): ## override the function , it must check if the site with this id have asset tracking as false , so change it first 
        site= serializer.validated_data['site']
        if not site.asset_tracking :
            site.asset_tracking = True
            site.save()
        serializer.save()



class UploadTagRfidUserView(APIView):
    """
    Upload an Excel file with multiple tag rfids.
    File should have columns: num_serie, date_install, type (passif , actif)
    """
    def post(self, request, format=None):
        file = request.FILES.get('file')
        site_id = request.data.get('site')
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        if not site_id:
            return Response({"error": "No site ID provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return Response({"error": "Site not found"}, status=status.HTTP_404_NOT_FOUND)
        try :
            df = pd.read_excel(file)

            # Convert rows to list of dicts
            tags_data = df.to_dict(orient='records')
        except Exception as e:
            return Response({"error": f"Invalid file format: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created_tags = []
        errors = []

        for i, tag_data in enumerate(tags_data):
            tag_data['site'] = site.id
            # fix date format if needed
            if isinstance(tag_data.get('date_install'), pd.Timestamp):
                tag_data['date_install'] = tag_data['date_install'].strftime('%Y-%m-%d')
            for key in ['type', 'num_serie']:
                if tag_data.get(key):
                    tag_data[key] = str(tag_data[key]).strip()
                    
            serializer = TagRfidSerializer(data=tag_data)
            if serializer.is_valid():
                serializer.save()
                created_tags.append(serializer.data)
            else:
                errors.append({"row": i+1, "errors": serializer.errors})

        if errors:
            return Response({"created": created_tags, "errors": errors}, status=status.HTTP_207_MULTI_STATUS)

        return Response({"created": created_tags}, status=status.HTTP_201_CREATED)