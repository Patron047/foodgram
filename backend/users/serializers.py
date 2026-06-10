import base64

from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework import serializers

from .models import Subscribe, User


class Base64ImageField(serializers.ImageField):
    """Поле для приема картинок в формате base64 через JSON"""
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format_, imgstr = data.split(';base64,')
            ext = format_.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        return super().to_internal_value(data)


class RecipeShortSerializer(serializers.Serializer):
    """Сериализатор для рецептов внутри подписки."""

    """Используется Serializer вместо ModelSerializer, чтобы избежать
    циклического импорта модели Recipe из приложения recipes."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    image = serializers.ImageField()
    cooking_time = serializers.IntegerField()


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
        if request and request.user.is_authenticated:
            return Subscribe.objects.filter(
                user=request.user, author=obj,
            ).exists()
        return False

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
        return None


class SubscribeSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
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

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Subscribe.objects.filter(
                user=request.user, author=obj,
            ).exists()
        return False

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
        return None

    def get_recipes_count(self, obj):
        """Возвращает общее количество рецептов автора"""
        return obj.recipes.count()

    def get_recipes(self, obj):
        """Возвращает список рецептов с учетом лимита recipes_limit"""
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        recipes_qs = obj.recipes.all()
        if limit:
            try:
                limit = int(limit)
                recipes_qs = recipes_qs[:limit]
            except ValueError:
                pass
        return RecipeShortSerializer(recipes_qs,
                                     many=True,
                                     context=self.context
                                     ).data
