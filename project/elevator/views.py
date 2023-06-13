from django.core.cache import cache

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from .models import ElevatorsModel, UserRequestModels
from .serializers import ElevatorSerializer, DoorChoicesSerializer, UserRequestSerialier

# Create your views here.

class InitializeElevators(viewsets.ModelViewSet):
    """
    API for initializing the elevators
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = ElevatorSerializer

    # Logic for install elevator
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


class UserRequests(viewsets.ModelViewSet):
    """
    API for user requests fetching requests, get and set elevator direction
    save user request.
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = ElevatorSerializer

    # Logic for get all user request
    @action(detail=False, methods=['GET'])
    def fetch_all_requests(self, request, *args, **kwargs):
        data = request.data
        elevator_name = data['elevator_name']
        user_requests = cache.get(f'destinations_{elevator_name}')
        return Response({"success": True, "requests": user_requests})

    # Logic for get elevator direction
    @action(detail=False, methods=['GET'])
    def get_elevator_direction(self, request=None, *args, **kwargs):
        data = request.data
        elevator_name = data['elevator_name']

        direction = cache.get(f"direction_{elevator_name}")

        if direction is None:
            direction = "stand_by"

        if request is None:
            return direction
        return Response({"success": True, "direction":direction})


    def set_elevator_direction(self, direction, elevator_name, *args, **kwargs):
        cache.set(f'direction_{elevator_name}', direction, timeout=None)

    # Logic for save user request
    @action(detail=False, methods=['POST'])
    def save_user_request(self, request, *args, **kwargs):
        elevator_name = request.data['elevator_name']
        user_request = request.data['floor']
        destinations = cache.get(f'destinations_{elevator_name}')

        elevator = self.queryset.filter(elevator_name=elevator_name).first()
        min_floor = elevator.first_floor
        max_floor = elevator.last_floor

        if elevator.maintenance:
            return Response({"success": False, "err_message": f"elevator {elevator_name} is under maintenance"}, status=status.HTTP_400_BAD_REQUEST)

        if user_request in range(min_floor, max_floor+1):
            if destinations is None:
                cache.set(f'destinations_{elevator_name}', {user_request}, timeout=None)
                UserRequestModels.objects.create(elevator_id=elevator.id, destination_floor=user_request)

            else:
                destinations.add(user_request)
                cache.set(f'destinations_{elevator_name}', set(destinations), timeout=None)
                UserRequestModels.objects.create(elevator_id=elevator.id, destination_floor=user_request)

            return Response({"success": True, "data": request.data, "destinations": cache.get(f'destinations_{elevator_name}')})

        raise Exception(f"user selected floor {user_request} is out of elevator floors")


class ElevatorFunctions(viewsets.ModelViewSet):
    """
    API for functioning of elevator
    """

    queryset = UserRequestModels.objects.all()
    serializer_class = UserRequestSerialier

    # Logic for checking next destinations
    @action(detail=False, methods=['POST'])
    def next_destinations(self, request=None, elevator_name=None, *args, **kwargs):
        if request is not None:
            data = request.data
            elevator_name = data['elevator_name']

        direction = cache.get(f'direction_{elevator_name}')
        elevator = ElevatorsModel.objects.filter(elevator_name=elevator_name).first()
        elevator_id = elevator.id
        maintenance = elevator.maintenance
        current_floor = elevator.current_floor

        next_floors, next_destination, final_destination, next_final_destination = None, None, None, None

        if maintenance:
            return Response({"Success": True, "message": "elevator is under maintenance"})

        all_destinations = self.queryset.filter(elevator_id=elevator_id).values('destination_floor')
        destinations = set()
        for destination in all_destinations:
            destinations.add(destination['destination_floor'])

        destinations = list(sorted(destinations)) if destinations else []

        direction = 'stand_by' if direction is None else direction

        # logic for checking no pending requests
        if len(destinations) == 0:
            cache.set(f'direction_{elevator_name}', 'stand_by', timeout=None)
            cache.set(f'next_destination_{elevator_name}', None, timeout=None)
            return Response({"success":True, "destinations": next_floors, "next_destination": next_destination,
                             "final_destination": final_destination, "current_floor": current_floor,
                             "moving_direction_final_destination": next_final_destination, "current_direction": direction})

        max_floor = elevator.last_floor
        min_floor = elevator.first_floor
        if current_floor == max_floor:
            direction = "moving down"
        elif current_floor == min_floor:
            direction = "moving up"

        request_max_floor = destinations[-1]
        request_min_floor = destinations[0]

        destinations.append(current_floor)
        destinations = list(sorted(set(destinations)))

        # Logic for if elevator is in stand_by
        if direction == "stand_by":
            direction = 'moving up' if (abs(current_floor - request_max_floor)) < (abs(current_floor - request_min_floor)) else 'moving down'
            cache.set(f'direction_{elevator_name}', direction, timeout=None)

        current_floor_index = destinations.index(current_floor)

        # Logic for elevator is moving down
        if direction == 'moving down':
            next_floors, next_destination, final_destination, next_final_destination, direction = self.moving_down(current_floor, max_floor, min_floor,
                                                                                                                    destinations, current_floor_index,
                                                                                                                    elevator_id, direction, elevator_name)

            return Response({"success":True, "destinations": next_floors, "next_destination": next_destination,
                             "final_destination": final_destination, "current_floor": current_floor,
                             "moving_direction_final_destination": next_final_destination, "current_direction": direction})


        # Logic for elevator is moving up
        if direction == 'moving up':
            next_floors, next_destination, final_destination, next_final_destination, direction = self.moving_up(current_floor, max_floor, min_floor,
                                                                                                                    destinations, current_floor_index,
                                                                                                                    elevator_id, direction, elevator_name)
            return Response({"success":True, "destinations": next_floors, "next_destination": next_destination,
                             "final_destination": final_destination, "current_floor": current_floor,
                             "moving_direction_final_destination": next_final_destination, "current_direction": direction})

        return Response({"success": True, "destinations": next_floors, "next_destination": next_destination,
                         "final_destination": final_destination, "current_floor": current_floor,
                         "moving_direction_final_destination": next_final_destination, "current_direction": direction})

    def moving_up(self, current_floor, max_floor, min_floor, destinations, current_floor_index, elevator_id, direction, elevator_name):
        next_floors = []
        next_destination, final_destination, next_final_destination = None, None, None

        if current_floor != max_floor:
            next_floors = destinations[current_floor_index + 1:]
            next_final_destination = max_floor
            final_destination = min_floor if current_floor > min_floor else max_floor

            next_destination = next_floors[0] if len(next_floors) else None

            if len(destinations[:current_floor_index]):
                next_floors += destinations[:current_floor_index]

        elif current_floor == max_floor:  # if elevator is already in top floor
            if len(destinations) == 1:
                direction = 'stand_by'
            else:
                direction = 'moving down'
                next_floors += destinations[::-1]
                next_final_destination = None
                final_destination = min_floor

                next_floors.remove(current_floor)
                next_destination = next_floors[0] if len(next_floors) else None


        destinations.remove(current_floor)
        cache.set(f'next_destination_{elevator_name}', next_destination, timeout=None)
        cache.set(f'direction_{elevator_name}', direction, timeout=None)
        cache.set(f'destinations_{elevator_name}', set(destinations), timeout=None)
        cache.set(f'next_destinations_{elevator_name}', destinations, timeout=None)

        return next_floors, next_destination, final_destination, next_final_destination, direction

    def moving_down(self, current_floor, max_floor, min_floor, destinations, current_floor_index, elevator_id, direction, elevator_name):
        next_floors = []
        next_destination, final_destination, next_final_destination = None, None, None

        if current_floor != min_floor:
            next_floors += destinations[:current_floor_index][::-1]

            next_final_destination = min_floor
            final_destination = min_floor if current_floor > max_floor else max_floor

            next_destination = next_floors[0] if len(next_floors) else None

            if len(destinations[current_floor_index + 1:]):
                next_floors += destinations[current_floor_index + 1:]

        elif current_floor == min_floor:  # if elevator is already in down floor
            if len(destinations) == 1:
                direction = 'stand_by'
            else:
                direction = 'moving up'
                next_floors += destinations
                next_final_destination = None
                final_destination = max_floor

                next_floors.remove(current_floor)
                next_destination = next_floors[0] if len(next_floors) else None

        destinations.remove(current_floor)

        cache.set(f'direction_{elevator_name}', direction, timeout=None)
        cache.set(f'next_destination_{elevator_name}', next_destination, timeout=None)
        cache.set(f'destinations_{elevator_name}', set(destinations), timeout=None)
        cache.set(f'next_destinations_{elevator_name}', destinations, timeout=None)

        return next_floors, next_destination, final_destination, next_final_destination, direction


    @action(detail=False, methods=['POST'])
    def destination_reached(self, request, *args, **kwargs):
        data = request.data
        elevator_name = data['elevator_name']
        current_floor = data['current_floor']
        destinations = cache.get(f'destinations_{elevator_name}')

        elevator = ElevatorsModel.objects.filter(elevator_name=elevator_name).first()
        if elevator is None:
            return Response({"success": False, "err_message": f"elevator {elevator_name} doesn't exists"}, status=status.HTTP_400_BAD_REQUEST)

        if destinations is None or current_floor not in destinations:
            return Response({"success": False, "err_message": "No such destinations in user request"}, status=status.HTTP_400_BAD_REQUEST)

        self.queryset.filter(elevator_id=elevator.id, destination_floor=current_floor).delete()
        ElevatorsModel.objects.update(elevator_name=elevator_name, current_floor=current_floor)
        destinations.remove(current_floor)

        next_destination = cache.get(f'next_destination_{elevator_name}')

        cache.set(f'current_floor_{elevator_name}', next_destination, timeout=None)
        cache.set(f'destinations_{elevator_name}', set(destinations), timeout=None)

        return Response({"success": True, "next_destination": next_destination, "current_floor": current_floor})


    # Logic for reach next destination
    @action(detail=False, methods=['POST'])
    def reach_next_destination(self, request, *args, **kwargs):
        data = request.data
        elevator_name = data['elevator_name']
        # self.next_destinations(elevator_name=elevator_name)

        current_floor = ElevatorsModel.objects.filter(elevator_name=elevator_name).first().current_floor
        next_destinations = cache.get(f'next_destinations_{elevator_name}')
        next_destination = cache.get(f'next_destination_{elevator_name}')

        elevator = ElevatorsModel.objects.filter(elevator_name=elevator_name).first()
        if elevator is None:
            return Response({"success": False, "err_message": f"elevator {elevator_name} doesn't exists"}, status=status.HTTP_400_BAD_REQUEST)

        if next_destination is not None:
            self.queryset.filter(elevator_id=elevator.id, destination_floor=current_floor).delete()

            current_floor = next_destination
            self.queryset.filter(elevator_id=elevator.id, destination_floor=current_floor).delete()
            ElevatorsModel.objects.filter(elevator_name=elevator_name).update(current_floor=current_floor)

            next_destinations.remove(current_floor)
            next_destination = next_destinations[0] if next_destinations else None
            cache.set(f"next_destination_{elevator_name}", next_destination, timeout=None)
            cache.set(f"next_destinations_{elevator_name}", next_destinations, timeout=None)

            return Response({"success": True, "message": "destination reached successfully", "next_destination": next_destination})

        cache.set(f"direction_{elevator_name}", "stand_by", timeout=None)
        return Response({"success": False, "err_message": "no more pending requests"})


    # Logic for get current floor
    @action(detail=False, methods=['GET'])
    def get_current_floor(self, request, *args, **kwargs):
        elevator_name = request.data['elevator_name']
        elevator = ElevatorsModel.objects.filter(elevator_name=elevator_name).first()

        if elevator is None:
            return Response({"success": False, "err_message": f"elevator {elevator_name} doesn't exists"}, status=status.HTTP_400_BAD_REQUEST)

        current_floor = elevator.current_floor
        return Response({"success": True, "current_floor": current_floor})


class Maintenance(viewsets.ModelViewSet):
    """
    API for setting the elevator under maintenance
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = ElevatorSerializer

    # to check the status of the elevator under maintenance or not
    @action(detail=False, methods=['GET'])
    def check_maintenance_status(self, request, *args, **kwargs):
        elevator_name = request.data.get('elevator_name')

        elevator_maintenance_status = self.queryset.filter(elevator_name=elevator_name).first()

        if elevator_maintenance_status is None:
            raise Exception(f"Elevator with the {elevator_name} dosen't exists")

        if elevator_maintenance_status.maintenance is False:
            status = "Elevator is working"
        else:
            cache.set(f'direction_{elevator_name}', 'stand_by', timeout=None)
            status = "Elevator is under maintenance"
        return Response({"success": True, "message":status})


    # Set the state of the elevator to be working or maintenance
    @action(detail=False, methods=['PUT', 'PATCH'])
    def set_maintenance(self, request, *args, **kwargs):
        data = request.data
        elevator_name = data['elevator_name']
        maintenance = data["maintenance"]
        elevator = self.queryset.filter(elevator_name=elevator_name).first()

        if elevator is None:
            return Response({"success": False, "err_message": f"elevator {elevator_name} doesn't exists"}, status=status.HTTP_400_BAD_REQUEST)

        self.queryset.filter(elevator_name=elevator_name).update(maintenance=maintenance)
        return Response({"success": True, "data": self.queryset.filter(elevator_name=elevator_name).values()})


class Door(viewsets.ModelViewSet):
    """
    API for elevator door close/open door
    """
    queryset = ElevatorsModel.objects.all()
    serializer_class = DoorChoicesSerializer

    # Logic for open or close door
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

