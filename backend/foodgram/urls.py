from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from api.v1.views.recipes import redirect_short_link

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.v1.urls')),
    path('s/<str:short_id>/', redirect_short_link, name='short-link-redirect'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT
                          )
