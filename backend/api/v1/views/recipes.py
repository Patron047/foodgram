import base64

from django.db.models import Prefetch, Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from recipes.models import (Favorite, Ingredient, IngredientInRecipe, Recipe,
                            ShoppingCart, Tag)
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (AllowAny, IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from ..filters import RecipeFilter
from ..permissions import IsAuthorOrReadOnly
from ..serializers.recipes import (FavoriteSerializer, IngredientSerializer,
                                   RecipeCreateUpdateSerializer,
                                   RecipeListSerializer,
                                   ShoppingCartSerializer, TagSerializer)


@api_view(['GET'])
@permission_classes((AllowAny,))
def redirect_short_link(request, short_id):
    try:
        padding = '=' * (4 - len(short_id) % 4) if len(short_id) % 4 else ''
        recipe_id = int(
            base64.urlsafe_b64decode(short_id + padding).decode()
        )
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
    permission_classes = (IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly)
    filterset_class = RecipeFilter
    filter_backends = (DjangoFilterBackend,)

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

    @action(detail=True,
            methods=('post', 'delete'),
            permission_classes=(IsAuthenticated,)
            )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if request.method == 'POST':
            serializer = FavoriteSerializer(
                data={'user': user.id, 'recipe': recipe.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            serializer_data = RecipeListSerializer(
                recipe,
                context={'request': request}
            ).data
            return Response(serializer_data, status=status.HTTP_201_CREATED)
        try:
            fav = Favorite.objects.get(user=user, recipe=recipe)
            fav.delete()
        except Favorite.DoesNotExist:
            raise ValidationError('Нет в избранном')
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True,
            methods=('post', 'delete'),
            permission_classes=(IsAuthenticated,)
            )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if request.method == 'POST':
            serializer = ShoppingCartSerializer(
                data={'user': user.id, 'recipe': recipe.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            serializer_data = RecipeListSerializer(
                recipe,
                context={'request': request}
            ).data
            return Response(serializer_data, status=status.HTTP_201_CREATED)
        try:
            cart = ShoppingCart.objects.get(user=user, recipe=recipe)
            cart.delete()
        except ShoppingCart.DoesNotExist:
            raise ValidationError('Нет в списке покупок')
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=('get',),
            permission_classes=(IsAuthenticated,))
    def download_shopping_cart(self, request):
        user = request.user
        shopping_list = IngredientInRecipe.objects.filter(
            recipe__in_shopping_carts__user=user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        ).order_by('ingredient__name')

        content_lines = [
            f"{index}. {item['ingredient__name']} "
            f"({item['ingredient__measurement_unit']}) — "
            f"{item['total_amount']}"
            for index, item in enumerate(shopping_list, 1)
        ]
        content = '\n'.join(['Список покупок:'] + content_lines) + '\n'

        response = HttpResponse(
            content, content_type='text/plain; charset=utf-8'
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
        path = reverse('short-link-redirect', kwargs={'short_id': short_id})
        short_link = request.build_absolute_uri(path)
        return Response({'short-link': short_link}, status=status.HTTP_200_OK)
