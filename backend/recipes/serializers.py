import base64

from django.core.files.base import ContentFile
from rest_framework import serializers
from users.serializers import UserProfileSerializer

from .models import (Favorite, Ingredient, IngredientInRecipe, Recipe,
                     ShoppingCart, Tag)


class Base64ImageField(serializers.ImageField):
    """Поле для приема картинок в формате base64 через JSON"""
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format_, imgstr = data.split(';base64,')
            ext = format_.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        return super().to_internal_value(data)


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


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = serializers.ListField(child=serializers.DictField())
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
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
                "Время приготовления должно быть больше 0"
            )
        return value

    def validate_tags(self, value):
        """Валидация тегов: проверка на пустоту и дубликаты"""
        if not value:
            raise serializers.ValidationError("Выберите хотя бы один тег")
        unique_tags = set(value)
        if len(unique_tags) != len(value):
            raise serializers.ValidationError("Теги не должны повторяться")
        return value

    def validate(self, attrs):
        """Проверяем обязательность ingredients при PATCH/PUT"""
        request = self.context.get('request')
        if request and request.method in ('PATCH', 'PUT'):
            raw_data = self.initial_data or {}
            if 'ingredients' not in raw_data:
                raise serializers.ValidationError("Это поле обязательно.")
            if 'tags' not in raw_data:
                raise serializers.ValidationError("Это поле обязательно.")
        return attrs

    def validate_ingredients(self, value):
        """Ручная валидация ингредиентов при создании/обновлении"""
        if not value:
            raise serializers.ValidationError("Нужен хотя бы один ингредиент")
        validated_ingredients = []
        seen_ids = set()

        for item in value:
            ing_id = item.get('id')
            amount = item.get('amount')
            if not ing_id:
                raise serializers.ValidationError("Укажите id ингредиента")
            if ing_id in seen_ids:
                raise serializers.ValidationError(
                    f"Ингредиент с id {ing_id} уже добавлен в рецепт"
                )
            seen_ids.add(ing_id)
            try:
                amount = int(amount)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Некорректное количество для ингредиента {ing_id}"
                )

            if amount < 1:
                raise serializers.ValidationError("Должно быть больше 0")
            try:
                ingredient = Ingredient.objects.get(id=ing_id)
            except Ingredient.DoesNotExist:
                raise serializers.ValidationError(
                    f"Ингредиент с id {ing_id} не существует"
                )
            validated_ingredients.append({
                'ingredient': ingredient,
                'amount': amount
            })
        return validated_ingredients

    def to_representation(self, instance):
        """Формируем полный ответ вручную"""
        tags_data = []
        for tag in instance.tags.all():
            tags_data.append({
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug
            })
        data = {
            'id': instance.id,
            'tags': tags_data,
            'author': UserProfileSerializer(instance.author,
                                            context=self.context
                                            ).data,
            'ingredients': [],
            'is_favorited': False,
            'is_in_shopping_cart': False,
            'name': instance.name,
            'image': None,
            'text': instance.text,
            'cooking_time': instance.cooking_time,
        }
        if instance.image:
            request = self.context.get('request')
            if request:
                data['image'] = request.build_absolute_uri(instance.image.url)
            else:
                data['image'] = instance.image.url
        read_serializer = IngredientInRecipeReadSerializer(
            instance.ingredient_list.all(), many=True
        )
        data['ingredients'] = read_serializer.data
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            data['is_favorited'] = Favorite.objects.filter(
                user=request.user, recipe=instance
            ).exists()
            data['is_in_shopping_cart'] = ShoppingCart.objects.filter(
                user=request.user, recipe=instance
            ).exists()
        return data

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)
        for ing_data in ingredients_data:
            IngredientInRecipe.objects.create(recipe=recipe, **ing_data)
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
            for ing_data in ingredients_data:
                IngredientInRecipe.objects.create(recipe=instance, **ing_data)

        return instance


class RecipeListSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    author = UserProfileSerializer(read_only=True)
    ingredients = IngredientInRecipeReadSerializer(
        source='ingredient_list',
        many=True,
        read_only=True
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

    def get_tags(self, obj):
        """Возвращаем теги как список объектов {id, name, slug}"""
        return [
            {'id': tag.id, 'name': tag.name, 'slug': tag.slug}
            for tag in obj.tags.all()
        ]

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user, recipe=obj
            ).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(
                user=request.user, recipe=obj
            ).exists()
        return False

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
        return None
