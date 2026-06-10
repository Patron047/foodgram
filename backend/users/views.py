from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Subscribe, User
from .serializers import (AvatarSerializer, SubscribeSerializer,
                          UserCreateSerializer, UserProfileSerializer)


class UserViewSet(DjoserUserViewSet):
    serializer_class = UserProfileSerializer
    create_serializer_class = UserCreateSerializer

    def get_permissions(self):
        """Разрешаем неавторизованным пользователям читать список и профиль"""
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return super().get_permissions()

    @action(
        detail=False,
        methods=['put', 'delete'],
        permission_classes=[IsAuthenticated],
        url_path='me/avatar'
    )
    def avatar(self, request, pk=None):
        user = request.user

        if request.method == 'PUT':
            serializer = AvatarSerializer(
                user, data=request.data, context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(
                {'avatar': request.build_absolute_uri(user.avatar.url)},
                status=status.HTTP_200_OK
            )

        if request.method == 'DELETE':
            if user.avatar:
                user.avatar.delete(save=True)
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)
        user = request.user

        if request.method == 'POST':
            if user == author:
                return Response(
                    {'detail': 'Нельзя подписаться на самого себя'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if Subscribe.objects.filter(user=user, author=author).exists():
                return Response(
                    {'detail': 'Вы уже подписаны на этого автора'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            Subscribe.objects.create(user=user, author=author)
            serializer = SubscribeSerializer(
                author, context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            subscription = Subscribe.objects.filter(
                user=user, author=author
            ).first()
            if not subscription:
                return Response(
                    {'detail': 'Вы не были подписаны на этого автора'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated],
    )
    def subscriptions(self, request):
        authors_ids = Subscribe.objects.filter(
            user=request.user
        ).values_list('author_id', flat=True)

        authors = User.objects.filter(id__in=authors_ids)
        page = self.paginate_queryset(authors)

        serializer = SubscribeSerializer(
            page, many=True, context={'request': request}
        )
        return self.get_paginated_response(serializer.data)
