from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views.recipes import (IngredientViewSet, RecipeViewSet, TagViewSet, 
                            redirect_short_link)
from .views.users import UserViewSet

router = SimpleRouter()
router.register('users', UserViewSet, basename='user')
router.register('tags', TagViewSet, basename='tag')
router.register('ingredients', IngredientViewSet, basename='ingredient')
router.register('recipes', RecipeViewSet, basename='recipe')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    path('s/<str:short_id>/', redirect_short_link, name='short-link-redirect'),
]
