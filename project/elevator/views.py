from django.shortcuts import render, HttpResponse
from django.core.cache import cache
from django.db.models import Q

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ElevatorsModel, UserRequestModels
from .serializers import ElevatorSerializer, DoorChoicesSerializer, UserRequestSerialier

# Create your views here.


class InitializeElevators(viewsets.ModelViewSet):
    """
    API for initializing the elevators
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = ElevatorSerializer


    @action(detail=False, methods=['POST'])
    def install_elevator(self, request, *args, **kwargs):
        data = request.data

        # logic to handle for one elevator
        if isinstance(data, dict):
            message, serialized_data = self.create_elevator(data)
            return Response({"message": message, "data": serialized_data})

        # logic to handle for more than one elevator

        if isinstance(data, list):
            responses = []
            for elevator in data:
                message, serialized_data = self.create_elevator(elevator)
                response = {
                    "message": message,
                    "data": serialized_data
                }
                responses.append(response)

            return Response(responses)

        return Response({"message": "body should should be in dict or in list of dicts"})

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def create_elevator(self, data):
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        message = "Elevator is succesfully installed"
        return message, serializer.data


class Maintenance(viewsets.ModelViewSet):
    """
    API for setting the elevator under maintenance
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = ElevatorSerializer

    # to check the status of the elevator under maintenance or not
    @action(detail=False, methods=['GET'], url_path='check')
    def check_maintenance_status(self, request, *args, **kwargs):
        elevator_name = request.data.get('elevator_name')

        elevator_maintenance_status = self.queryset.filter(elevator_name=elevator_name).first()
        if elevator_maintenance_status is None:
            raise Exception(f"Elevator with the {elevator_name} dosen't exists")

        if elevator_maintenance_status is False:
            status = "Elevator is working"
        else:
            cache.set('direction', 'stand_by', timeout=None)
            status = "Elevator is under maintenance"
        return Response({"success": True, "elevator_status":status})

    # Set the state of the elevator to be working or maintenance
    @action(detail=False, methods=['PUT', 'PATCH'])
    def set_maintenance(self, request, *args, **kwargs):
        elevator_name = request.data.get('elevator_name')
        elevator = self.queryset.filter(elevator_name=elevator_name).first()

        if elevator is None:
            raise Exception(f"Elevator with the {elevator_name} dosen't exists")

        self.queryset.filter(elevator_name=elevator_name).update(maintenance=True)
        return Response({"success": True, "data": request.data})


class Door(viewsets.ModelViewSet):
    """
    API for elevator door close/open door
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = DoorChoicesSerializer

    @action(detail=False, methods=['PUT', 'PATCH'])
    def open_or_close_door(self, request, *args, **kwargs):
        serializer = DoorChoicesSerializer(data = request.data)
        serializer.is_valid(raise_exception=True)

        # logic to update the door status
        data = serializer.data
        elevator_name = data['elevator_name']
        door = data['door']
        elevator = self.queryset.filter(elevator_name = elevator_name).first()

        if elevator is not None:
            self.queryset.filter(elevator_name=elevator_name).update(door=door)

        updated_data = self.queryset.filter(elevator_name=elevator_name).values()
        return Response({"success": True, "data": updated_data})

class UserRequests(viewsets.ModelViewSet):
    """
    API for user requests fetching requests, get and set elevator direction
    save user request.
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = ElevatorSerializer


    @action(detail=False, methods=['GET'])
    def fetch_all_requests(self, requests, *args, **kwargs):
        user_requests = cache.get('destinations')
        return Response({"success": True, "requests": user_requests})


    @action(detail=False, methods=['GET'])
    def get_elevator_direction(self, request=None, *args, **kwargs):
        direction = cache.get("direction")

        if direction is None:
            direction = "stand_by"

        if request is None:
            return direction
        return Response({"success": True, "direction":direction})


    def set_elevator_direction(self, direction, *args, **kwargs):
        cache.set('direction', direction, timeout=None)


    @action(detail=False, methods=['POST'])
    def save_user_request(self, request, *args, **kwargs):
        elevator_name = request.data['elevator_name']
        user_request = request.data['floor']
        next_destinations = cache.get('destinations')

        elevator = self.queryset.filter(elevator_name=elevator_name).first()
        min_floor = elevator.first_floor
        max_floor = elevator.last_floor

        if user_request in range(min_floor, max_floor):
            if next_destinations is None:
                cache.set('destinations', {user_request}, timeout=None)
                UserRequests.objects.create(elevator_id=elevator.id, destination_floor=user_request)

            else:
                next_destinations.add(user_request)
                cache.set('destinations', next_destinations, timeout=None)
                UserRequests.objects.create(elevator_id=elevator.id, destination_floor=user_request)

            return Response({"success": True, "data": request.data, "next destinations": cache.get('destinations')})

        raise Exception(f"user selected floor {user_request} is out of elevator floors")


class ElevatorFunctions(viewsets.ModelViewSet):
    """
    API for functioning of elevator
    """

    queryset = UserRequestModels.objects.all()
    serializer_class = UserRequestSerialier

    @action(detail=False, methods=['POST'])
    def elevator(self, request, *args, **kwargs):
        direction_class = UserRequests()
        direction = cache.get('direction')
        destinations = cache.get('destinations')
        destinations = destinations if destinations else []

        max_floor = destinations[-1]
        min_floor = destinations[0]

        data = request.data
        current_floor = data['current_floor']
        door = data['door']
        elevator_name = data['elevator_name']

        destinations.append(current_floor)
        destinations = list(sorted(destinations))

        elevator_id = self.queryset.filter(elevator_name=elevator_name).id

        self.queryset.create(elevator_id=elevator_id, current_floor=current_floor)
        print(elevator_id, destinations, max_floor, min_floor)

        # login for checking no pending requests
        if len(destinations) == 1:
            cache.set('direction', 'stand_by', timeout=None)
            return Response({"success":True, "destinations": None, "next_destination": None, "final_destination": None, "moving_direction_final_destination": None, "current_direction": direction})

        # Logic for if elevator is in stand_by
        if direction == "stand_by":
            direction = 'moving up' if (abs(current_floor - max_floor)) < (abs(current_floor - min_floor))  else 'moving down'
            direction_class.set_elevator_direction(direction)

        next_floors = []
        next_destination, final_destination, next_final_destination = None, None, None
        current_floor_index = destinations.index(current_floor)

        # Logic for elevator is moving down
        if direction == 'moving down':
            if current_floor != min_floor:
                next_floors += destinations[:current_floor_index][::-1]
                next_destination = next_floors[0]
                next_final_destination = min_floor
                final_destination = max_floor

                if len(destinations[current_floor_index+1:]):
                    next_floors += destinations[current_floor_index+1:]

            elif current_floor == min_floor: # if elevator is already in down floor
                if len(destinations) == 1:
                    direction = 'stand_by'
                else:
                    direction = 'moving up'
                    next_floors += destinations
                    next_destination = next_floors[0]
                    next_final_destination = None
                    final_destination = max_floor
            cache.set('direction', direction, timeout=None)

            return Response({"success":True, "destinations": next_floors, "next_destination": next_destination, "final_destination": final_destination, "moving_direction_final_destination": next_final_destination, "current_direction": direction})

        # Logic for elevator is moving up
        if direction == 'moving up':
            if current_floor != max_floor:
                next_floors = destinations[current_floor_index+1:]
                next_destination = destinations[0]
                next_final_destination = max_floor
                final_destination = min_floor

                if len(destinations[:current_floor_index]):
                    next_floors += destinations[:current_floor_index]

            elif current_floor == max_floor: # if elevator is already in top floor
                if len(destinations) == 1:
                    direction = 'stand_by'
                else:
                    direction = 'moving down'
                    next_floors += destinations[::-1]
                    next_destination = next_floors[0]
                    next_final_destination = None
                    final_destination = min_floor

            cache.set('next_destination', next_destination)
            cache.set('direction', direction, timeout=None)

            return Response({"success":True, "destinations": next_floors, "next_destination": next_destination, "final_destination": final_destination, "moving_direction_final_destination": next_final_destination, "current_direction": direction})

        return Response({"success": True, "direction": direction, "next_floors": next_floors, "destinations": destinations})

    @action(detail=False, methods=['POST'])
    def destination_visited(self, request, *args, **kwargs):
        data = request.data
        elevator_name = data['elevator_name']
        current_floor = data['current_floor']

        elevator = ElevatorsModel.objects.filter(elevator_name=elevator_name).first()
        if elevator is None:
            raise Exception(f"elevator with name {elevator_name} dosen't exists")

        self.queryset.delete(elevator_id=elevator.id, current_floor=current_floor)
        next_destination = cache.get('next_destination')

        if next_destination is not None:
            self.queryset.create(elevator_id=elevator.id, current_floor=next_destination)

        return Response({"success":True, "next_destination": next_destination})

    @action(detail=False, methods=['GET'])
    def get_current_floor(self, request, *args, **kwargs):
        elevator_name = request.data['elevator_name']
        elevator = ElevatorsModel.objects.filter(elevator_name=elevator_name).first()

        if elevator is None:
            raise Exception(f"elevator with {elevator_name} name dosen't exists")

        current_floor = elevator.current_floor

        return Response({"success": True, "current_floor": current_floor})