import secrets
from django.conf import settings
from django.http import HttpResponse, JsonResponse


class StagingAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/healthz/' and request.method in {'GET', 'HEAD'}:
            return HttpResponse('ok', content_type='text/plain')
        expected = getattr(settings, 'STAGING_GATE_SECRET', '')
        supplied = request.META.get('HTTP_X_TELLBOOK_STAGING_GATE', '')
        if not expected or not secrets.compare_digest(supplied.encode(), expected.encode()):
            return JsonResponse({'detail': 'Private staging access required.'}, status=403)
        request.staging_authorized = True
        response = self.get_response(request)
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return response
