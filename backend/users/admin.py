from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Subscribe, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    search_fields = ('email', 'username')
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')


@admin.register(Subscribe)
class SubscribeAdmin(admin.ModelAdmin):
    list_display = ('user', 'author')
    search_fields = ('user__username',
                     'user__email',
                     'author__username', 'author__email'
                     )
