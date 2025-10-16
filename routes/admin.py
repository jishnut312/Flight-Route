from django.contrib import admin
from .models import Airport, Route

@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("source", "destination", "distance_km", "duration_min")
    list_filter = ("source", "destination")

# Register your models here.
