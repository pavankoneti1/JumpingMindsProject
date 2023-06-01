from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import ElevatorsModel, DoorStatus, UserRequestModels

class ElevatorSerializer(ModelSerializer):
    """
    Serializer for initializing the elevators
    """
    class Meta:
        model = ElevatorsModel
        fields = "__all__"

class DoorChoicesSerializer(ModelSerializer):
    """
    Serializer for door choices
    """

    elevator_name = serializers.CharField(max_length=100)
    class Meta:
        model = ElevatorsModel
        fields = ("door", "elevator_name")

class UserRequestSerialier(ModelSerializer):
    class Meta:
        model = UserRequestModels
        fields = "__all__"