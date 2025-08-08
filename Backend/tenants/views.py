# tenants/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import AddClientWithUserSerializer , ClientListSerializer , ClientDetailSerializer
from rest_framework.permissions import IsAdminUser
from rest_framework import generics
from .models import Client
# i should come back here and add exeptions instead of much returns (as good practice)

class AddClientView(APIView):
    #permission_classes = [IsAdminUser]  
    def post(self, request):
        serializer = AddClientWithUserSerializer(data=request.data) # call the serializer with the data on the body 
        if serializer.is_valid(): # if data is valide 
            client = serializer.save() # save the new client 
            # i.e : create new tennant -> it will creat new schema
            #  for the client , the schma name will be the entrprise name
            #  after ma nsgmoh in the serializer
            return Response({"message": "Client and user created", "schema": client.schema_name}, status=status.HTTP_201_CREATED) # 201 : user created i.e : schema created
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) # else error 
    

class ClientListView(generics.ListAPIView) : 
    queryset= Client.objects.all()
    serializer_class = ClientListSerializer


class ClientDetailView(generics.RetrieveAPIView) : 
    queryset = Client.objects.filter()
    serializer_class = ClientDetailSerializer
    lookup_field = 'pk'
    

    #auto return using RetriveApiView