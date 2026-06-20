from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthorOrReadOnly(BasePermission):
    """Разрешает редактирование только автору объекта."""

    def has_permission(self, request, view):
        # Разрешаем безопасные методы (GET, HEAD, OPTIONS) всем
        if request.method in SAFE_METHODS:
            return True
        # Для остальных методов требуется авторизация
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Безопасные методы уже разрешены в has_permission
        if request.method in SAFE_METHODS:
            return True
        # Изменять или удалять может только автор
        return obj.author == request.user
