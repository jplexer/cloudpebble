from django.urls import path, re_path, include

from root import views

app_name = 'root'
urlpatterns = [
    re_path(r'^$', views.index, name='index'),
    re_path(r'^i18n/', include('django.conf.urls.i18n'))
]
