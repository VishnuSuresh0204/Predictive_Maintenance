from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


class Login(AbstractUser):
    usertype = models.CharField(max_length=50)  # Admin / Technician / Organization
    viewpassword = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.username


class Organization(models.Model):
    login = models.OneToOneField(Login, on_delete=models.CASCADE)
    organization_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    industry_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization_name"]

    def __str__(self):
        return self.organization_name


class MachineType(models.Model):
    """e.g. CNC Machine, Hydraulic Press, Conveyor Motor, Industrial Pump."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Machine(models.Model):
    STATUS_CHOICES = [
        ("Operational", "Operational"),
        ("Under Maintenance", "Under Maintenance"),
        ("Stopped", "Stopped"),
        ("Decommissioned", "Decommissioned"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    machine_name = models.CharField(max_length=150)
    machine_type = models.ForeignKey(
        MachineType, on_delete=models.SET_NULL, null=True, blank=True
    )
    serial_number = models.CharField(max_length=100, unique=True)
    manufacturer = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)
    installation_date = models.DateField()
    operating_hours = models.FloatField(default=0, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Operational")
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["machine_name"]

    def __str__(self):
        return f"{self.machine_name} ({self.serial_number})"

    @property
    def age_in_years(self):
        from django.utils import timezone
        return round((timezone.now().date() - self.installation_date).days / 365.25, 1)

    @property
    def latest_prediction(self):
        return self.prediction_set.order_by("-prediction_date").first()

    @property
    def latest_reading(self):
        return self.sensordata_set.order_by("-recorded_at").first()



 
class SensorData(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    temperature = models.FloatField(help_text="degrees Celsius")
    vibration = models.FloatField(help_text="mm/s", validators=[MinValueValidator(0)])
    pressure = models.FloatField(help_text="bar", validators=[MinValueValidator(0)])
    rotational_speed = models.FloatField(help_text="RPM", validators=[MinValueValidator(0)])
    torque = models.FloatField(help_text="Nm", validators=[MinValueValidator(0)])
    power_consumption = models.FloatField(help_text="kW", validators=[MinValueValidator(0)])
    operating_hours = models.FloatField(
        default=0, validators=[MinValueValidator(0)],
        help_text="Cumulative run hours at the time of this reading"
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["machine", "-recorded_at"])]
 
    def __str__(self):
        return f"{self.machine.machine_name} @ {self.recorded_at:%Y-%m-%d %H:%M}"
 
 
class Prediction(models.Model):
    RISK_CHOICES = [
        ("Normal", "Normal"),
        ("Warning", "Warning"),
        ("High Risk", "High Risk"),
    ]
 
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    sensor_data = models.OneToOneField(
        SensorData, on_delete=models.CASCADE, null=True, blank=True
    )
    failure_probability = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES, default="Normal")
    predicted_failure = models.BooleanField(default=False)
    recommended_action = models.TextField(blank=True)
    top_factors = models.TextField(
        blank=True,
        help_text="Comma separated features that pushed the risk up, from feature importance"
    )
    model_version = models.CharField(max_length=50, blank=True)
    processing_time_ms = models.PositiveIntegerField(null=True, blank=True)
    prediction_date = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ["-prediction_date"]
        indexes = [models.Index(fields=["machine", "-prediction_date"])]
 
    def __str__(self):
        return f"{self.machine.machine_name} - {self.risk_level}"
 
    @property
    def probability_percent(self):
        return round(self.failure_probability * 100, 2)