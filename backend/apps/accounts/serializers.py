"""Accounts serializers: user, registration, JWT-with-user."""
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "is_active",
                  "is_staff", "created_at")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "email", "username", "password", "role")
        read_only_fields = ("id",)

    def create(self, validated):
        password = validated.pop("password")
        user = User(**validated)
        user.set_password(password)
        user.save()
        return user


class TokenWithUserSerializer(TokenObtainPairSerializer):
    """JWT pair + embedded user claims and the serialized user in the body."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
