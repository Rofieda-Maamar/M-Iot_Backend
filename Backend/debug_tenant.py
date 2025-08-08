# Backend/debug_tenant.py
class DebugTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print("DEBUG-MW: Host:", request.get_host(), "PATH:", request.path,
              "META[HTTP_HOST]:", request.META.get('HTTP_HOST'),
              "tenant:", getattr(request, "tenant", None))
        return self.get_response(request)
