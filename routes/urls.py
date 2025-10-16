from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('airports/add/', views.add_airport, name='add_airport'),
    path('routes/add/', views.add_route, name='add_route'),
    path('airports/add-with-route/', views.add_airport_and_route, name='add_airport_and_route'),
    path('routes/search/', views.search_nodes, name='search_nodes'),
]
