"""Accounts serializers: user, registration, login."""
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    workspace_ids = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "is_active", "workspace_ids")
        read_only_fields = fields

    def get_workspace_ids(self, obj):
        return [str(w.id) for w in obj.workspaces.all()]


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


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs["email"], password=attrs["password"]
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled")
        attrs["user"] = user
        return attrs
