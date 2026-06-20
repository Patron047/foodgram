import base64

from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .models import Recipe


def redirect_short_link(request, short_id):
    """
    Перенаправляет по короткой ссылке на страницу рецепта.

    Размещено в recipes/views.py, так как редирект относится
    к уровню представлений, а не к API.
    """
    try:
        padding = '=' * (4 - len(short_id) % 4) if len(short_id) % 4 else ''
        decoded_bytes = base64.urlsafe_b64decode(short_id + padding)
        recipe_id = int(decoded_bytes.decode())
    except (ValueError, UnicodeDecodeError):
        from django.http import Http404
        raise Http404('Некорректная короткая ссылка')
    get_object_or_404(Recipe, id=recipe_id)
    return HttpResponseRedirect(f'/recipes/{recipe_id}/')
