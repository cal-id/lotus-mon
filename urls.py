from django.conf.urls import url
from . import views
from django.conf.urls.static import static
from django.conf import settings

app_name = 'monitor'
urlpatterns = [
    url(r'^$', views.index, name="index"),
    url(r'^register-crash/(?P<host>host[0-9]{3}\.jc\.rl\.ac\.uk)$',
        views.registerCrash, name="registerCrash"),
    url(r'^saved-crash/(?P<i>[0-9]+$)', views.detailOfCrash,
        name="savedCrash")
] + (static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) +
     static(settings.STATIC_URL, document_root=settings.STATIC_ROOT))
