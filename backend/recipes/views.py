import base64

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .models import Recipe


def _decode_short_id(short_id):
    """Декодирует short_id в integer id рецепта."""
    padding = '=' * (4 - len(short_id) % 4) if len(short_id) % 4 else ''
    decoded_bytes = base64.urlsafe_b64decode(short_id + padding)
    return int(decoded_bytes.decode())


def redirect_short_link(request, short_id):
    """Перенаправляет по короткой ссылке на страницу рецепта."""
    try:
        recipe_id = _decode_short_id(short_id)
    except (ValueError, UnicodeDecodeError, OverflowError):
        raise Http404('Некорректная короткая ссылка')
    get_object_or_404(Recipe, id=recipe_id)
    return HttpResponseRedirect(f'/recipes/{recipe_id}/')
