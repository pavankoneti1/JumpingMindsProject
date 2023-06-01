from django.db import models

# Create your models here.

class DoorStatus(models.TextChoices):
    """
    Choices for the door opened or closed
    """
    OPEN = "opened"
    CLOSE = "closed"

class ElevatorsModel(models.Model):
    """
    Model for initializing the elevators
    """
    DOOR_STATUS = (
        ("OPEN", "opened"),
        ("CLOSE", "closed")
    )

    elevator_name = models.CharField(max_length=100, unique=True)
    maintenance = models.BooleanField(default=False)
    current_floor = models.IntegerField()
    first_floor = models.IntegerField()
    last_floor = models.IntegerField()
    door = models.CharField(max_length=10, choices=DOOR_STATUS)


class UserRequestModels(models.Model):
    """
    Model for user requests for elevator
    """

    elevator = models.ForeignKey(ElevatorsModel, on_delete=models.CASCADE)
    destination_floor = models.IntegerField()

