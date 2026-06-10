from django.db.models import Prefetch
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from .filters import RecipeFilter
from .models import Favorite, IngredientInRecipe, Recipe, ShoppingCart
from .permissions import IsAuthorOrReadOnly
from .serializers import RecipeCreateUpdateSerializer, RecipeListSerializer


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filterset_class = RecipeFilter
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        """Оптимизируем запросы, подгружая связи для сериализатора"""
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

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if request.method == 'POST':
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'detail': 'Уже в избранном'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            Favorite.objects.create(user=user, recipe=recipe)
            serializer = RecipeListSerializer(
                recipe, context={'request': request}
            )
            return Response(
                serializer.data, status=status.HTTP_201_CREATED
            )
        fav = Favorite.objects.filter(user=user, recipe=recipe).first()
        if not fav:
            return Response(
                {'detail': 'Нет в избранном'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fav.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if request.method == 'POST':
            if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'detail': 'Уже в списке покупок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            ShoppingCart.objects.create(user=user, recipe=recipe)
            serializer = RecipeListSerializer(
                recipe, context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        cart = ShoppingCart.objects.filter(user=user, recipe=recipe).first()
        if not cart:
            return Response(
                {'detail': 'Нет в списке покупок'},
                status=status.HTTP_400_BAD_REQUEST
            )
        cart.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
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
            name = item.ingredient.name
            unit = item.ingredient.measurement_unit
            amount = item.amount
            key = f"{name} ({unit})"
            if key in shopping_list:
                shopping_list[key] += amount
            else:
                shopping_list[key] = amount
        lines = ["Список покупок:\n"]
        for index, (ingredient_info, total_amount) in enumerate(
            shopping_list.items(), 1
        ):
            lines.append(f"{index}. {ingredient_info} — {total_amount}")
        content = "\n".join(lines)
        response = HttpResponse(
            content, content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    @action(
        detail=True, methods=['get'],
        permission_classes=[IsAuthenticatedOrReadOnly],
        url_path='get-link', url_name='get-link'
    )
    def get_link(self, request, pk=None):
        import hashlib
        from urllib.parse import urljoin
        recipe = self.get_object()
        hash_object = hashlib.sha256(str(recipe.id).encode())
        short_id = hash_object.hexdigest()[:8]
        base_url = f"{request.scheme}://{request.get_host()}"
        short_link = urljoin(base_url, f"/s/{short_id}/")
        return Response({'short-link': short_link}, status=status.HTTP_200_OK)
