from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.conf import settings
from django.http import JsonResponse

urlpatterns = [
    path('health', lambda request: JsonResponse({'ok': True})),
    re_path(r'^ide/', include('ide.urls', namespace='ide')),
    re_path(r'^accounts/', include('auth.urls')),
    re_path(r'^qr/', include('qr.urls', namespace='qr')),
    path('', include('root.urls', namespace='root')),
    path('', include('social_django.urls', namespace='social')),
    re_path(r'^i18n/', include('django.conf.urls.i18n')),
]
