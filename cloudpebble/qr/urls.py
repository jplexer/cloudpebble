from django.urls import path, re_path

from qr import views

app_name = 'qr'
urlpatterns = [

    re_path('$^', views.render, name='render')
]
