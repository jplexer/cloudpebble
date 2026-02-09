from django.urls import path, re_path, include
from django.conf import settings
from django.contrib.auth import views as auth_views

from auth import views

reg_view = views.IdeRegistrationMissingView.as_view() if settings.SOCIAL_AUTH_PEBBLE_REQUIRED else views.IdeRegistrationView.as_view()

urlpatterns = [
    re_path(r'^register/?$', reg_view, name="registration_register"),
    re_path(r'^logout/?$', views.logout_view, name="logout"),
    re_path(r'^api/login$', views.login_action, name="login"),
    re_path(r'^api/firebase-login$', views.firebase_login, name="firebase_login"),
    # Password reset views
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    re_path(r'', include('registration.backends.simple.urls'))
]
