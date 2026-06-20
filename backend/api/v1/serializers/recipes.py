from recipes.models import (Favorite, Ingredient, IngredientInRecipe, Recipe,
                            ShoppingCart, Tag)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .common import Base64ImageField
from .users import UserProfileSerializer


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ('user', 'recipe')

    def validate(self, attrs):
        user = attrs.get('user')
        recipe = attrs.get('recipe')
        if Favorite.objects.filter(user=user, recipe=recipe).exists():
            raise ValidationError('Уже в избранном')
        return attrs


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe')

    def validate(self, attrs):
        user = attrs.get('user')
        recipe = attrs.get('recipe')
        if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
            raise ValidationError('Уже в списке покупок')
        return attrs


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientInRecipeReadSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class IngredientWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class RecipeListSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserProfileSerializer(read_only=True)
    ingredients = IngredientInRecipeReadSerializer(
        source='ingredient_list', many=True, read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart',
            'name', 'image', 'text', 'cooking_time',
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if hasattr(obj, 'is_favorited_flag'):
                return obj.is_favorited_flag
            return (
                hasattr(obj, 'is_favorited_list')
                and bool(obj.is_favorited_list)
            )
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if hasattr(obj, 'is_in_shopping_cart_flag'):
                return obj.is_in_shopping_cart_flag
            return (
                hasattr(obj, 'is_in_shopping_cart_list')
                and bool(obj.is_in_shopping_cart_list)
            )
        return False

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
        return None


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = IngredientWriteSerializer(many=True, write_only=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, write_only=True
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'ingredients', 'tags', 'image',
            'name', 'text', 'cooking_time',
        )

    def validate_cooking_time(self, value):
        if value < 1:
            raise serializers.ValidationError(
                'Время приготовления должно быть больше 0'
            )
        return value

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError('Выберите хотя бы один тег')
        unique_tags = set(value)
        if len(unique_tags) != len(value):
            raise serializers.ValidationError('Теги не должны повторяться')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.method in ('PATCH', 'PUT'):
            raw_data = self.initial_data or {}
            if 'ingredients' not in raw_data:
                raise serializers.ValidationError('Это поле обязательно.')
            if 'tags' not in raw_data:
                raise serializers.ValidationError('Это поле обязательно.')
        return attrs

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError('Нужен хотя бы один ингредиент')
        ingredient_ids = [item['id'] for item in value]
        if len(set(ingredient_ids)) != len(ingredient_ids):
            seen_ids = set()
            for item in value:
                ing_id = item['id']
                if ing_id in seen_ids:
                    raise serializers.ValidationError(
                        f'Ингредиент с id {ing_id} уже добавлен в рецепт'
                    )
                seen_ids.add(ing_id)
        existing_ingredients = Ingredient.objects.filter(
            id__in=ingredient_ids
        )
        existing_ids = {ing.id for ing in existing_ingredients}
        missing_ids = set(ingredient_ids) - existing_ids
        if missing_ids:
            missing_ids_str = ', '.join(str(ing_id) for ing_id in missing_ids)
            error_message = f'Ингредиенты с id {missing_ids_str} не существуют'
            raise serializers.ValidationError(error_message)
        ingredients_dict = {ing.id: ing for ing in existing_ingredients}
        validated_ingredients = [
            {
                'ingredient': ingredients_dict[item['id']],
                'amount': item['amount']
            }
            for item in value
        ]
        return validated_ingredients

    def _save_ingredients(self, recipe, ingredients_data):
        """Сохраняет ингредиенты для рецепта используя bulk_create."""
        ingredient_in_recipe_objects = [
            IngredientInRecipe(recipe=recipe, **ing_data)
            for ing_data in ingredients_data
        ]
        IngredientInRecipe.objects.bulk_create(ingredient_in_recipe_objects)

    def create(self, validated_data):
        request = self.context.get('request')
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        recipe = Recipe.objects.create(author=request.user, **validated_data)
        recipe.tags.set(tags_data)
        self._save_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.set(tags_data)

        if ingredients_data is not None:
            instance.ingredient_list.all().delete()
            self._save_ingredients(instance, ingredients_data)
        return instance
