# tenants/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import AddClientWithUserSerializer , ClientListSerializer , ClientDetailSerializer
from rest_framework.permissions import IsAdminUser
from rest_framework import generics
from rest_framework.exceptions import NotFound
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


"""
    Retrieve a single Client's details.
    - Basic info comes from the public schema.
    - Related info (telephone, email, created_at, sites) comes from the tenant schema.
"""

class ClientDetailView(generics.RetrieveAPIView) : 
    serializer_class = ClientDetailSerializer
    lookup_field = 'pk'

    """
        Fetch the Client instance from the public schema using the pk from the URL.
        Store the tenant schema_name for later use (in the serilaizer ) in serializer context.
    """
    def get_object(self):
        client_id = self.kwargs.get(self.lookup_field) # grabs the pk from the URL path.
        try:
            client = Client.objects.get(pk=client_id)  # from public schema
        except Client.DoesNotExist: #if no client found with this id 
            raise NotFound("Client not found") # rause 404 not found 
        self.schema_name = client.schema_name  # save the schema name 
        return client # return the client object to be serialized 

    """
        Extend DRF's default serializer context to include the tenant schema_name.
        This allows the serializer to switch to the correct schema when accessing
        tenant-specific fields like telephone, email, sites.
        """
    def get_serializer_context(self):
        context = super().get_serializer_context() # to get DRF’s normal context (request, format, view).
        if hasattr(self, 'schema_name'): #check if self.schema_name was set in get_object().
            context['schema_name'] = self.schema_name #adds schema_name to the context dictionary.
        return context # return the updated context 
    # after that , drf will call the serializer with : ClientDetailSerializer(instance, context) #and the context have the schema name 
    # the serializer will call the to_representation() which with its role call the getters ( which they are defined on the serilaizer)
    #auto return using RetriveApiView
    # DRF execution flow:
# 1. URL matches ClientDetailView -> dispatch() called
# 2. dispatch() determines method -> calls retrieve()
# 3. retrieve() calls get_object() ( ovveride )-> fetch Client from public schema
# 4. get_serializer_context() called -> schema_name added
# 5. Serializer instantiated: ClientDetailSerializer(instance, context)
# 6. Serializer.to_representation() called -> triggers SerializerMethodField getters
#    - Inside getters, with schema_context(schema_name) switches to tenant schema
# 7. retrieve() wraps serializer data in Response() -> returned as HTTP response