from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from rest_framework.permissions import AllowAny


class BaseSocialLoginView(SocialLoginView):
    permission_classes = [AllowAny]


class GitHubLoginView(BaseSocialLoginView):
    adapter_class = GitHubOAuth2Adapter


class GoogleLoginView(BaseSocialLoginView):
    adapter_class = GoogleOAuth2Adapter
