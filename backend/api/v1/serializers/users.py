from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from recipes.models import Recipe
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from users.models import Subscribe

from .common import Base64ImageField

User = get_user_model()


class RecipeShortSerializer(serializers.ModelSerializer):
    """Сериализатор для рецептов внутри подписки."""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField()

    class Meta:
        model = User
        fields = ('avatar',)


class UserCreateSerializer(BaseUserCreateSerializer):
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('email',
                  'id',
                  'username',
                  'first_name',
                  'last_name',
                  'password'
                  )


class UserProfileSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username',
            'first_name', 'last_name',
            'is_subscribed', 'avatar',
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.following.filter(user_id=request.user.pk).exists()

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
        return None


class SubscribeCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания подписки с валидацией."""
    class Meta:
        model = Subscribe
        fields = ('author',)

    def validate_author(self, value):
        request = self.context.get('request')
        user = request.user
        if user == value:
            raise ValidationError('Нельзя подписаться на самого себя')
        if user.subscriber.filter(author=value).exists():
            raise ValidationError('Вы уже подписаны на этого автора')
        return value


class SubscribeSerializer(UserProfileSerializer):
    recipes_count = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username',
            'first_name', 'last_name',
            'is_subscribed', 'avatar',
            'recipes_count', 'recipes',
        )

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        """Возвращает список рецептов с учетом лимита recipes_limit"""
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        recipes_qs = obj.recipes.all()
        if limit:
            try:
                limit = int(limit)
            except ValueError:
                limit = None
            if limit:
                recipes_qs = recipes_qs[:limit]
        return RecipeShortSerializer(recipes_qs,
                                     many=True,
                                     context=self.context
                                     ).data
