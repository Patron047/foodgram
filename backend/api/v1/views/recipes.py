import base64

from django.db.models import Exists, OuterRef, Prefetch, Sum
from django.http import HttpResponse
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from recipes.models import (Favorite, Ingredient, IngredientInRecipe, Recipe,
                            ShoppingCart, Tag)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ..filters import RecipeFilter
from ..permissions import IsAuthorOrReadOnly
from ..serializers.recipes import (FavoriteSerializer, IngredientSerializer,
                                   RecipeCreateUpdateSerializer,
                                   RecipeListSerializer,
                                   ShoppingCartSerializer, TagSerializer)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    pagination_class = None

    def get_queryset(self):
        queryset = Ingredient.objects.all()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class RecipePagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'limit'


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthorOrReadOnly,)
    filterset_class = RecipeFilter
    filter_backends = (DjangoFilterBackend,)
    pagination_class = RecipePagination
    ordering = ('-pub_date',)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = RecipeListSerializer(
            serializer.instance,
            context={'request': request}
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers
                        )

    def get_queryset(self):
        user = self.request.user
        queryset = Recipe.objects.all().select_related('author')
        queryset = queryset.prefetch_related(
            'tags',
            'ingredient_list__ingredient',
        )
        if user.is_authenticated:
            is_favorited_param = self.request.query_params.get('is_favorited')
            is_in_shopping_cart_param = (
                self.request.query_params.get('is_in_shopping_cart')
            )

            if is_favorited_param == '1':
                queryset = queryset.filter(favorited_by__user=user)
            if is_in_shopping_cart_param == '1':
                queryset = queryset.filter(in_shopping_carts__user=user)

            fav_subquery = Favorite.objects.filter(user=user,
                                                   recipe=OuterRef('pk')
                                                   )
            cart_subquery = ShoppingCart.objects.filter(user=user,
                                                        recipe=OuterRef('pk')
                                                        )
            queryset = queryset.annotate(
                is_favorited_flag=Exists(fav_subquery),
                is_in_shopping_cart_flag=Exists(cart_subquery)
            )
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
        serializer = FavoriteSerializer(
            data={'user': user.id, 'recipe': recipe.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        Favorite.objects.filter(user=user, recipe=recipe).delete()
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
        serializer = ShoppingCartSerializer(
            data={'user': user.id, 'recipe': recipe.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        ShoppingCart.objects.filter(user=user, recipe=recipe).delete()
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
            f"{index}. {item.get('ingredient__name', '')} "
            f"({item.get('ingredient__measurement_unit', '')}) — "
            f"{item.get('total_amount', '')}"
            for index, item in enumerate(shopping_list, 1)
        ]
        content = '\n'.join(('Список покупок:', *content_lines)) + '\n'

        response = HttpResponse(
            content, content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    @action(detail=True,
            methods=('get',),
            permission_classes=(AllowAny,),
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
