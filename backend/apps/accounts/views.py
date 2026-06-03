"""Accounts views: register, login (JWT), me."""
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer, TokenWithUserSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class LoginView(TokenObtainPairView):
    serializer_class = TokenWithUserSerializer
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)
