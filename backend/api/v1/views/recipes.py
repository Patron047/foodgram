import base64
from urllib.parse import urljoin

from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import (AllowAny,
                                        IsAuthenticated,
                                        IsAuthenticatedOrReadOnly
                                        )
from rest_framework.response import Response

from recipes.models import (Favorite, Ingredient, IngredientInRecipe,
                            Recipe, ShoppingCart, Tag)
from ..filters import RecipeFilter
from ..permissions import IsAuthorOrReadOnly
from ..serializers.recipes import (IngredientSerializer,
                                   RecipeCreateUpdateSerializer,
                                   RecipeListSerializer,
                                   TagSerializer
                                   )


@api_view(['GET'])
@permission_classes((AllowAny,))
def redirect_short_link(request, short_id):
    try:
        padding = '=' * (4 - len(short_id) % 4) if len(short_id) % 4 else ''
        recipe_id = int(base64.urlsafe_b64decode(short_id + padding).decode())
    except (ValueError, Exception):
        return Response(
            {'detail': 'Некорректная короткая ссылка'},
            status=status.HTTP_404_NOT_FOUND
        )
    recipe = get_object_or_404(Recipe, id=recipe_id)
    return HttpResponseRedirect(f'/api/recipes/{recipe.id}/')


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeListSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly)
    filterset_class = RecipeFilter
    filter_backends = (DjangoFilterBackend,)  # Кортеж!

    def get_queryset(self):
        user = self.request.user
        queryset = Recipe.objects.all().select_related('author')
        queryset = queryset.prefetch_related(
            'tags',
            'ingredient_list__ingredient',
        )
        if user.is_authenticated:
            fav_prefetch = Prefetch(
                'favorited_by',
                queryset=Favorite.objects.filter(user=user),
                to_attr='is_favorited_list'
            )
            cart_prefetch = Prefetch(
                'in_shopping_carts',
                queryset=ShoppingCart.objects.filter(user=user),
                to_attr='is_in_shopping_cart_list'
            )
            queryset = queryset.prefetch_related(fav_prefetch, cart_prefetch)
        return queryset

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RecipeCreateUpdateSerializer
        return RecipeListSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True,
            methods=('post', 'delete'),
            permission_classes=(IsAuthenticated,)
            )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if request.method == 'POST':
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response({'detail': 'Уже в избранном'},
                                status=status.HTTP_400_BAD_REQUEST
                                )
            Favorite.objects.create(user=user, recipe=recipe)
            serializer = RecipeListSerializer(recipe,
                                              context={'request': request}
                                              )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        fav = Favorite.objects.filter(user=user, recipe=recipe).first()
        if not fav:
            return Response({'detail': 'Нет в избранном'},
                            status=status.HTTP_400_BAD_REQUEST
                            )
        fav.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True,
            methods=('post', 'delete'),
            permission_classes=(IsAuthenticated,)
            )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if request.method == 'POST':
            if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
                return Response({'detail': 'Уже в списке покупок'},
                                status=status.HTTP_400_BAD_REQUEST
                                )
            ShoppingCart.objects.create(user=user, recipe=recipe)
            serializer = RecipeListSerializer(recipe,
                                              context={'request': request}
                                              )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        cart = ShoppingCart.objects.filter(user=user, recipe=recipe).first()
        if not cart:
            return Response({'detail': 'Нет в списке покупок'},
                            status=status.HTTP_400_BAD_REQUEST
                            )
        cart.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False,
            methods=('get',),
            permission_classes=(IsAuthenticated,)
            )
    def download_shopping_cart(self, request):
        user = request.user
        recipe_ids = ShoppingCart.objects.filter(
            user=user
        ).values_list('recipe_id', flat=True)
        ingredients_in_recipes = IngredientInRecipe.objects.filter(
            recipe_id__in=recipe_ids
        ).select_related('ingredient')
        shopping_list = {}
        for item in ingredients_in_recipes:
            key = (
                f"{item.ingredient.name} "
                f"({item.ingredient.measurement_unit})"
            )
            shopping_list[key] = shopping_list.get(key, 0) + item.amount
        lines = ["Список покупок:\n"]
        for index, (info, total) in enumerate(shopping_list.items(), 1):
            lines.append(f"{index}. {info} — {total}")
        response = HttpResponse("\n".join(lines),
                                content_type='text/plain; charset=utf-8'
                                )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    @action(detail=True,
            methods=('get',),
            permission_classes=(IsAuthenticatedOrReadOnly,),
            url_path='get-link', url_name='get-link'
            )
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_id = base64.urlsafe_b64encode(
            str(recipe.id).encode()
        ).decode().rstrip('=')
        base_url = f"{request.scheme}://{request.get_host()}"
        short_link = urljoin(base_url, f"/s/{short_id}/")
        return Response({'short-link': short_link}, status=status.HTTP_200_OK)
