from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        login_value = username or kwargs.get(user_model.USERNAME_FIELD)

        if not login_value or not password:
            return None

        try:
            user = user_model._default_manager.get(
                Q(username__iexact=login_value) | Q(email__iexact=login_value)
            )
        except user_model.DoesNotExist:
            user_model().set_password(password)
            return None
        except user_model.MultipleObjectsReturned:
            user = (
                user_model._default_manager.filter(email__iexact=login_value)
                .order_by("id")
                .first()
            )

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
