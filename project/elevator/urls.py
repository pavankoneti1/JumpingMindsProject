from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'install', InitializeElevators, basename='install elevator')
router.register(r'maintenance', Maintenance, basename='maintanence')
router.register(r'door', Door, basename='door')
router.register(r'userrequests', UserRequests, basename='user requests')
router.register(r'elevator', ElevatorFunctions, basename='elevator functions')

app_name='elevator'
urlpatterns = [
    path('', include(router.urls)),
]