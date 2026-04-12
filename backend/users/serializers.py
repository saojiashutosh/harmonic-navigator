from rest_framework import serializers
from harmonic_navigator.serializers import HarmonicBaseSerializer
from .models import Users, UsersDevices
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _


class UsersSerializer(HarmonicBaseSerializer):
    # TODO
    # def validate(self, attrs):
    #     return super().validate(attrs)

    class Meta:
        model = Users
        read_only_fields = ('email', 'is_superuser')
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'firstName',
            'lastName',
            'email',
            'level',
            'is_active',
            'is_staff',
            'is_superuser',
            'profilePicture',
        )
        get_fields = (
            'id',
            'createdAt',
            'updatedAt',
            'firstName',
            'lastName',
            'email',
            'level',
            'is_active',
            'is_staff',
            'is_superuser',
            'profilePicture',
        )
        list_fields = (
            'id',
            'createdAt',
            'updatedAt',
            'firstName',
            'lastName',
            'email',
            'level',
            'is_active',
            'is_staff',
            'is_superuser',
            'profilePicture',
        )

    def create(self, validated_data):
        # print("I am authenticated", validated_data, flush=True)
        user = Users.objects.create(**validated_data)
        user.set_password(validated_data["password"])
        user.save()
        return user


class UsersDevicesSerializer(HarmonicBaseSerializer):
    class Meta:
        model = UsersDevices
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'userId',
            'deviceId',
            'token',
            'deviceType',
            'language',
        )
        get_fields = fields
        list_fields = fields


class RegisterSerializer(serializers.ModelSerializer):

    class Meta:
        model = Users
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'firstName',
            'lastName',
            'email',
            'password',
            'level',
            "password",
            'is_active',
            'is_staff',
            'is_superuser',
            'profilePicture',
        )

    def create(self, validated_data):
        # print("I am authenticated", validated_data, flush=True)
        user = Users.objects.create(**validated_data)
        user.set_password(validated_data["password"])
        user.save()
        return user


class UpdatePasswordSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password])
    confirmPassword = serializers.CharField(write_only=True, required=True)
    oldPassword = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Users
        fields = ('oldPassword', 'password', 'confirmPassword')

    def validate(self, attrs):
        if attrs['password'] != attrs['confirmPassword']:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."})
        self._validate_old_password(attrs['oldPassword'])
        return attrs

    def _validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                {"oldPassword": "Old password is not correct"})
        return value

    def update(self, instance, validated_data):
        user = self.context['request'].user
        if user.pk != instance.pk:
            raise serializers.ValidationError(
                {"authorize": "You dont have permission for this user."})

        instance.set_password(validated_data['password'])
        instance.save()
        return instance


# admin user serialzer
class UpdateAdminStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = Users
        fields = (
            'id',
            'is_superuser',
            'level',
        )


class UploadProfilePictureSerializer(serializers.ModelSerializer):

    class Meta:
        model = Users
        fields = ('id', 'profilePicture')


class ResendOTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = (
            'email',
            'otp',
        )

    def validate(self, data,):
        user = Users.objects.filter(email=data['email'])
        if not user.exists():
            raise serializers.ValidationError(
                _("User with email %(email)s does not exist") % {'email': data['email']})
        if (user.first().isVerified):
            raise serializers.ValidationError(
                _("User with email %(email)s is already verified") % {'email': data['email']})
        return data


class VerifyAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = (
            'email',
            'otp',
        )

    def update(self, instance, validated_data):
        instance.is_active = True
        instance.isVerified = True
        instance.save()
        return instance

    def validate(self, data,):
        user = Users.objects.filter(email=data['email'])
        if user.first().otp != data["otp"]:
            raise serializers.ValidationError(
                _("The otp entered does not match"))
        if not user.exists():
            raise serializers.ValidationError(
                _("User with email %(email)s does not exist") % {'email': data['email']})
        if (user.first().isVerified):
            raise serializers.ValidationError(
                _("User with email %(email)s is already verified") % {'email': data['email']})
        return data
