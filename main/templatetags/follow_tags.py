from django import template
from main.models import Follow

register = template.Library()

@register.filter
def user_follows(user, other_user):
    """Return True if 'user' follows 'other_user'."""
    if not user.is_authenticated:
        return False
    return Follow.objects.filter(follower=user, following=other_user).exists()