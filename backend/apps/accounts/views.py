"""Accounts views: register, login, refresh, me.

Response shape matches the frontend AuthContext: {user, tokens:{access_token,
refresh_token, token_type}} for login/register; {access_token, refresh_token}
for refresh.
"""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


def _tokens_for(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "token_type": "bearer",
    }


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, "tokens": _tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response({"user": UserSerializer(user).data, "tokens": _tokens_for(user)})


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("refresh_token") or request.data.get("refresh")
        if not token:
            return Response({"detail": "refresh_token required"}, status=400)
        try:
            refresh = RefreshToken(token)
            return Response(
                {"access_token": str(refresh.access_token), "refresh_token": str(refresh)}
            )
        except Exception:
            return Response({"detail": "Invalid or expired token"}, status=401)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)
