from django.db import models


class Airport(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Route(models.Model):
    source = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='departures')
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='arrivals')
    POSITION_LEFT = 'LEFT'
    POSITION_RIGHT = 'RIGHT'
    POSITION_CHOICES = (
        (POSITION_LEFT, 'Left'),
        (POSITION_RIGHT, 'Right'),
    )
    position = models.CharField(max_length=5, choices=POSITION_CHOICES)
    distance_km = models.FloatField(default=0)
    duration_min = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = (
            ('source', 'destination'),
            ('source', 'position'),
        )

    def __str__(self) -> str:
        return f"{self.source.code} -> {self.destination.code}"

# Create your models here.
