
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from django.db.models import Avg, Count
from django.utils import timezone

from .models import *



# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_current_org(request):
    """Get the organization linked to the logged-in user."""
    if not request.user.is_authenticated:
        return None

    return Organization.objects.filter(
        login=request.user
    ).first()


def is_admin(request):
    """Check whether the logged-in user is an admin."""
    return request.user.is_authenticated and (
        request.user.is_superuser
        or request.user.usertype == "Admin"
    )


def organization_required(request):
    """Check login and retrieve the current organization."""
    if not request.user.is_authenticated:
        return None

    return get_current_org(request)


# =========================================================
# HOME
# =========================================================

def home(request):
    features = [
        {
            "icon": "📡",
            "title": "Sensor Data Logging",
            "desc": (
                "Record temperature, vibration, pressure, "
                "rotational speed, torque and power consumption."
            ),
        },
        {
            "icon": "🤖",
            "title": "AI Failure Prediction",
            "desc": (
                "Estimate machine failure probability "
                "using a trained machine learning model."
            ),
        },
        {
            "icon": "⚠️",
            "title": "Risk Classification",
            "desc": (
                "Classify machine conditions as Normal, "
                "Warning or High Risk."
            ),
        },
        {
            "icon": "🛠️",
            "title": "Machine Management",
            "desc": (
                "Register machines and monitor their "
                "operating status and sensor readings."
            ),
        },
    ]

    return render(
        request,
        "home.html",
        {"features": features}
    )


# =========================================================
# ORGANIZATION REGISTRATION
# =========================================================

def register(request):
    if request.method == "POST":

        username = request.POST.get(
            "username", ""
        ).strip()

        password = request.POST.get(
            "password", ""
        )

        organization_name = request.POST.get(
            "organization_name", ""
        ).strip()

        email = request.POST.get(
            "email", ""
        ).strip()

        phone = request.POST.get(
            "phone", ""
        ).strip()

        address = request.POST.get(
            "address", ""
        ).strip()

        industry_type = request.POST.get(
            "industry_type", ""
        ).strip()

        # Validate required fields
        if not all([
            username,
            password,
            organization_name,
            email,
            phone,
            address,
            industry_type,
        ]):
            messages.error(
                request,
                "Please fill in all required fields."
            )
            return render(request, "register.html")

        if Login.objects.filter(
            username=username
        ).exists():
            messages.error(
                request,
                "Username already exists."
            )
            return render(request, "register.html")

        try:
            # Create login account
            user = Login.objects.create_user(
                username=username,
                password=password,
                usertype="Organization",
            )

            # Create organization profile
            Organization.objects.create(
                login=user,
                organization_name=organization_name,
                email=email,
                phone=phone,
                address=address,
                industry_type=industry_type,
            )

        except Exception:
            messages.error(
                request,
                "Registration failed. Please try again."
            )
            return render(request, "register.html")

        messages.success(
            request,
            "Organization registered successfully. "
            "Please log in."
        )

        return redirect("/login/")

    return render(request, "register.html")


# =========================================================
# LOGIN
# =========================================================

def login_view(request):
    if request.user.is_authenticated:
        if is_admin(request):
            return redirect("/admin-home/")

        return redirect("/org-home/")

    if request.method == "POST":

        username = request.POST.get(
            "username", ""
        ).strip()

        password = request.POST.get(
            "password", ""
        )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            auth_login(request, user)

            messages.success(
                request,
                f"Welcome back, {user.username}!"
            )

            if is_admin(request):
                return redirect("/admin-home/")

            if user.usertype == "Organization":
                return redirect("/org-home/")

            auth_logout(request)

            messages.error(
                request,
                "Your account does not have an assigned role."
            )

            return redirect("/login/")

        messages.error(
            request,
            "Invalid username or password."
        )

    return render(request, "login.html")


# =========================================================
# LOGOUT
# =========================================================

def logout_view(request):
    auth_logout(request)

    messages.info(
        request,
        "You have been logged out."
    )

    return redirect("/login/")


# =========================================================
# ORGANIZATION DASHBOARD
# =========================================================

def org_home(request):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        if is_admin(request):
            return redirect("/admin-home/")

        messages.error(
            request,
            "Organization profile not found."
        )

        return redirect("/login/")

    machines = Machine.objects.filter(
        organization=org
    ).select_related("machine_type")

    predictions = Prediction.objects.filter(
        organization=org
    )

    recent_predictions = (
        predictions
        .select_related("machine", "sensor_data")
        .order_by("-prediction_date")[:5]
    )

    context = {
        "org": org,
        "machines": machines,
        "recent_predictions": recent_predictions,

        "total_machines": machines.count(),

        "operational_count": machines.filter(
            status="Operational"
        ).count(),

        "maintenance_count": machines.filter(
            status="Under Maintenance"
        ).count(),

        "stopped_count": machines.filter(
            status="Stopped"
        ).count(),

        "total_predictions": predictions.count(),

        "normal_count": predictions.filter(
            risk_level="Normal"
        ).count(),

        "warning_count": predictions.filter(
            risk_level="Warning"
        ).count(),

        "high_risk_count": predictions.filter(
            risk_level="High Risk"
        ).count(),
    }

    return render(
        request,
        "ORGANIZATION/home.html",
        context
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

def admin_home(request):
    if not request.user.is_authenticated:
        return redirect("/login/")

    if not is_admin(request):
        messages.error(
            request,
            "Admin access required."
        )

        return redirect("/org-home/")

    organizations = Organization.objects.all().order_by(
        "-created_at"
    )

    machines = Machine.objects.all()
    predictions = Prediction.objects.all()

    context = {
        "organizations": organizations,

        "total_orgs_count": organizations.count(),
        "total_machines_sum": machines.count(),
        "total_predictions_sum": predictions.count(),

        "total_high_risk_sum": predictions.filter(
            risk_level="High Risk"
        ).count(),

        "total_warning_sum": predictions.filter(
            risk_level="Warning"
        ).count(),

        "total_normal_sum": predictions.filter(
            risk_level="Normal"
        ).count(),
    }

    return render(
        request,
        "ADMIN/home.html",
        context
    )


# =========================================================
# ORGANIZATION PROFILE
# =========================================================

def profile(request):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    if request.method == "POST":

        org.organization_name = request.POST.get(
            "organization_name",
            org.organization_name
        ).strip()

        org.email = request.POST.get(
            "email",
            org.email
        ).strip()

        org.phone = request.POST.get(
            "phone",
            org.phone
        ).strip()

        org.address = request.POST.get(
            "address",
            org.address
        ).strip()

        org.industry_type = request.POST.get(
            "industry_type",
            org.industry_type
        ).strip()

        org.save()

        messages.success(
            request,
            "Organization profile updated successfully."
        )

        return redirect("/profile/")

    total_machines = Machine.objects.filter(
        organization=org
    ).count()

    return render(
        request,
        "ORGANIZATION/profile.html",
        {
            "org": org,
            "total_machines": total_machines,
        }
    )


# =========================================================
# REGISTER MACHINE
# =========================================================

def register_machine(request):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    machine_types = MachineType.objects.all()

    if request.method == "POST":

        machine_name = request.POST.get(
            "machine_name", ""
        ).strip()

        serial_number = request.POST.get(
            "serial_number", ""
        ).strip()

        if not machine_name or not serial_number:
            messages.error(
                request,
                "Machine name and serial number are required."
            )

            return redirect("/register-machine/")

        if Machine.objects.filter(
            serial_number=serial_number
        ).exists():
            messages.error(
                request,
                "Serial number already exists."
            )

            return redirect("/register-machine/")

        try:
            operating_hours = float(
                request.POST.get(
                    "operating_hours", 0
                ) or 0
            )

            if operating_hours < 0:
                raise ValueError

        except (ValueError, TypeError):
            messages.error(
                request,
                "Enter valid operating hours."
            )

            return redirect("/register-machine/")

        installation_date = request.POST.get(
            "installation_date"
        )

        if not installation_date:
            messages.error(
                request,
                "Installation date is required."
            )

            return redirect("/register-machine/")

        machine = Machine.objects.create(
            organization=org,

            machine_name=machine_name,

            machine_type_id=(
                request.POST.get("machine_type_id")
                or None
            ),

            serial_number=serial_number,

            manufacturer=request.POST.get(
                "manufacturer", ""
            ).strip(),

            location=request.POST.get(
                "location", ""
            ).strip(),

            installation_date=installation_date,

            operating_hours=operating_hours,

            status=request.POST.get(
                "status", "Operational"
            ),
        )

        messages.success(
            request,
            f"Machine '{machine.machine_name}' registered."
        )

        return redirect("/machines/")

    return render(
        request,
        "ORGANIZATION/register_machine.html",
        {
            "org": org,
            "machine_types": machine_types,
        }
    )


# =========================================================
# MACHINE LIST
# =========================================================

def machine_list(request):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    machines = (
        Machine.objects
        .filter(organization=org)
        .select_related("machine_type")
        .order_by("machine_name")
    )

    machine_data = []

    for machine in machines:
        machine_data.append({
            "machine": machine,
            "latest_prediction": machine.latest_prediction,
            "latest_reading": machine.latest_reading,

            "reading_count": SensorData.objects.filter(
                machine=machine
            ).count(),
        })

    context = {
        "org": org,
        "machine_data": machine_data,

        "total_machines": machines.count(),

        "operational_count": machines.filter(
            status="Operational"
        ).count(),

        "maintenance_count": machines.filter(
            status="Under Maintenance"
        ).count(),

        "stopped_count": machines.filter(
            status="Stopped"
        ).count(),
    }

    return render(
        request,
        "ORGANIZATION/machine_list.html",
        context
    )


# =========================================================
# MACHINE DETAIL
# =========================================================

def machine_detail(request, machine_id):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    machine = get_object_or_404(
        Machine,
        id=machine_id,
        organization=org
    )

    readings = SensorData.objects.filter(
        machine=machine
    ).order_by("-recorded_at")[:20]

    predictions = (
        Prediction.objects
        .filter(
            machine=machine,
            organization=org
        )
        .select_related("sensor_data")
        .order_by("-prediction_date")[:10]
    )

    averages = SensorData.objects.filter(
        machine=machine
    ).aggregate(
        avg_temperature=Avg("temperature"),
        avg_vibration=Avg("vibration"),
        avg_pressure=Avg("pressure"),
        avg_rotational_speed=Avg("rotational_speed"),
        avg_torque=Avg("torque"),
        avg_power_consumption=Avg("power_consumption"),
    )

    context = {
        "org": org,
        "machine": machine,
        "readings": readings,
        "predictions": predictions,
        "averages": averages,

        "latest_prediction": machine.latest_prediction,
        "latest_reading": machine.latest_reading,
    }

    return render(
        request,
        "ORGANIZATION/machine_detail.html",
        context
    )


# =========================================================
# EDIT MACHINE
# =========================================================

def edit_machine(request, machine_id):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    machine = get_object_or_404(
        Machine,
        id=machine_id,
        organization=org
    )

    if request.method == "POST":

        machine.machine_name = request.POST.get(
            "machine_name",
            machine.machine_name
        ).strip()

        machine.manufacturer = request.POST.get(
            "manufacturer",
            machine.manufacturer
        ).strip()

        machine.location = request.POST.get(
            "location",
            machine.location
        ).strip()

        machine.status = request.POST.get(
            "status",
            machine.status
        )

        machine.machine_type_id = (
            request.POST.get("machine_type_id")
            or None
        )

        try:
            operating_hours = float(
                request.POST.get(
                    "operating_hours",
                    machine.operating_hours
                )
            )

            if operating_hours < 0:
                raise ValueError

            machine.operating_hours = operating_hours

        except (ValueError, TypeError):
            messages.error(
                request,
                "Enter valid operating hours."
            )

            return redirect(
                f"/edit-machine/{machine.id}/"
            )

        machine.save()

        messages.success(
            request,
            "Machine updated successfully."
        )

        return redirect(
            f"/machine/{machine.id}/"
        )

    return render(
        request,
        "ORGANIZATION/edit_machine.html",
        {
            "org": org,
            "machine": machine,
            "machine_types": MachineType.objects.all(),
        }
    )


# =========================================================
# DELETE MACHINE
# =========================================================

def delete_machine(request, machine_id):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    machine = get_object_or_404(
        Machine,
        id=machine_id,
        organization=org
    )

    if request.method == "POST":
        machine_name = machine.machine_name
        machine.delete()

        messages.success(
            request,
            f"Machine '{machine_name}' deleted successfully."
        )

    return redirect("/machines/")


# =========================================================
# ADD SENSOR DATA + AI PREDICTION
# =========================================================

def add_sensor_data(request, machine_id=None):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    machines = Machine.objects.filter(
        organization=org
    ).exclude(
        status="Decommissioned"
    )

    selected_machine = None
    if machine_id:
        selected_machine = Machine.objects.filter(id=machine_id, organization=org).first()

    if request.method == "POST":

        machine = get_object_or_404(
            Machine,
            id=request.POST.get("machine_id"),
            organization=org
        )

        numeric_fields = [
            "temperature",
            "vibration",
            "pressure",
            "rotational_speed",
            "torque",
            "power_consumption",
            "operating_hours",
        ]

        values = {}

        try:
            for field in numeric_fields:

                raw_value = request.POST.get(field)

                if raw_value is None or raw_value == "":
                    raise ValueError

                values[field] = float(raw_value)

                if values[field] < 0:
                    raise ValueError

        except (ValueError, TypeError):
            messages.error(
                request,
                "Enter valid non-negative sensor readings."
            )

            return render(
                request,
                "ORGANIZATION/add_sensor_data.html",
                {
                    "org": org,
                    "machines": machines,
                }
            )

        # Save sensor readings
        reading = SensorData.objects.create(
            machine=machine,
            **values
        )

        # Update cumulative machine operating hours
        if values["operating_hours"] > machine.operating_hours:
            machine.operating_hours = values["operating_hours"]

            machine.save(
                update_fields=["operating_hours"]
            )

        # Prepare input for the ML model
        features = dict(values)

        features["machine_age"] = machine.age_in_years

        # Run prediction
        try:
            result = predict_failure(features)

        except FileNotFoundError:
            messages.warning(
                request,
                "Sensor data saved, but the AI model "
                "is unavailable."
            )

            return redirect(
                f"/machine/{machine.id}/"
            )

        except Exception as error:
            messages.error(
                request,
                f"Prediction failed: {error}"
            )

            return redirect(
                f"/machine/{machine.id}/"
            )

        # Save prediction result
        prediction = Prediction.objects.create(
            machine=machine,
            organization=org,
            sensor_data=reading,

            failure_probability=result[
                "failure_probability"
            ],

            risk_level=result["risk_level"],

            predicted_failure=result[
                "predicted_failure"
            ],

            recommended_action=result.get(
                "recommended_action", ""
            ),

            top_factors=result.get(
                "top_factors", ""
            ),

            model_version=result.get(
                "model_version", ""
            ),

            processing_time_ms=result.get(
                "processing_time_ms"
            ),
        )

        messages.success(
            request,
            (
                f"Prediction completed: "
                f"{prediction.risk_level} "
                f"({prediction.probability_percent}% "
                f"failure probability)."
            )
        )

        return redirect(
            f"/prediction/{prediction.id}/"
        )

    return render(
        request,
        "ORGANIZATION/add_sensor_data.html",
        {
            "org": org,
            "machines": machines,
            "selected_machine": selected_machine,
            "selected_machine_id": machine_id,
        }
    )


# =========================================================
# PREDICTION DETAIL
# =========================================================

def prediction_detail(request, prediction_id):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    prediction = get_object_or_404(
        Prediction.objects.select_related(
            "machine",
            "sensor_data"
        ),
        id=prediction_id,
        organization=org
    )

    return render(
        request,
        "ORGANIZATION/prediction_detail.html",
        {
            "org": org,
            "prediction": prediction,
        }
    )


# =========================================================
# PREDICTION HISTORY
# =========================================================

def prediction_history(request):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)

    if not org:
        return redirect("/login/")

    predictions = (
        Prediction.objects
        .filter(organization=org)
        .select_related("machine", "sensor_data")
        .order_by("-prediction_date")
    )

    machine_id = request.GET.get("machine_id")

    if machine_id:
        predictions = predictions.filter(
            machine_id=machine_id
        )

    context = {
        "org": org,
        "predictions": predictions,

        "machines": Machine.objects.filter(
            organization=org
        ),

        "selected_machine_id": machine_id,

        "total_predictions": predictions.count(),

        "normal_count": predictions.filter(
            risk_level="Normal"
        ).count(),

        "warning_count": predictions.filter(
            risk_level="Warning"
        ).count(),

        "high_risk_count": predictions.filter(
            risk_level="High Risk"
        ).count(),
    }

    return render(
        request,
        "ORGANIZATION/prediction_history.html",
        context
    )


# =========================================================
# ADMIN: ORGANIZATION LIST
# =========================================================

def admin_organizations(request):
    if not is_admin(request):
        return redirect("/login/")

    organizations = Organization.objects.all().order_by(
        "-created_at"
    )

    org_data = []

    for org in organizations:

        machines = Machine.objects.filter(
            organization=org
        )

        predictions = Prediction.objects.filter(
            organization=org
        )

        org_data.append({
            "org": org,

            "machine_count": machines.count(),

            "prediction_count": predictions.count(),

            "normal_count": predictions.filter(
                risk_level="Normal"
            ).count(),

            "warning_count": predictions.filter(
                risk_level="Warning"
            ).count(),

            "high_risk_count": predictions.filter(
                risk_level="High Risk"
            ).count(),
        })

    return render(
        request,
        "ADMIN/organizations.html",
        {
            "org_data": org_data,
            "total_count": organizations.count(),
        }
    )


# =========================================================
# ADMIN: MACHINE LIST
# =========================================================

def admin_machines(request):
    if not is_admin(request):
        return redirect("/login/")

    machines = (
        Machine.objects
        .select_related(
            "organization",
            "machine_type"
        )
        .all()
        .order_by("-registered_at")
    )

    machine_data = []

    for machine in machines:
        machine_data.append({
            "machine": machine,

            "latest_prediction": machine.latest_prediction,

            "latest_reading": machine.latest_reading,

            "prediction_count": Prediction.objects.filter(
                machine=machine
            ).count(),
        })

    context = {
        "machine_data": machine_data,

        "organizations": Organization.objects.all(),

        "total_machines": machines.count(),

        "operational_count": machines.filter(
            status="Operational"
        ).count(),

        "maintenance_count": machines.filter(
            status="Under Maintenance"
        ).count(),

        "stopped_count": machines.filter(
            status="Stopped"
        ).count(),
    }

    return render(
        request,
        "ADMIN/machines.html",
        context
    )


# =========================================================
# ADMIN: PREDICTION LIST
# =========================================================

def admin_predictions(request):
    if not is_admin(request):
        return redirect("/login/")

    predictions = (
        Prediction.objects
        .select_related(
            "machine",
            "organization",
            "sensor_data"
        )
        .all()
        .order_by("-prediction_date")
    )

    context = {
        "predictions": predictions,

        "organizations": Organization.objects.all(),

        "normal_results": predictions.filter(
            risk_level="Normal"
        ),

        "warning_results": predictions.filter(
            risk_level="Warning"
        ),

        "high_risk_results": predictions.filter(
            risk_level="High Risk"
        ),

        "total_predictions": predictions.count(),
    }

    return render(
        request,
        "ADMIN/predictions.html",
        context
    )


# =========================================================
# ADMIN: REPORTS
# =========================================================

def admin_reports(request):
    if not is_admin(request):
        return redirect("/login/")

    predictions = Prediction.objects.all()

    total_predictions = predictions.count()

    total_high_risk = predictions.filter(
        risk_level="High Risk"
    ).count()

    overall_failure_rate = (
        round(
            total_high_risk / total_predictions * 100,
            2
        )
        if total_predictions
        else 0
    )

    # Risk level breakdown
    risk_stats = (
        predictions
        .values("risk_level")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Predictions grouped by machine type
    machine_type_stats = (
        predictions
        .filter(
            machine__machine_type__isnull=False
        )
        .values("machine__machine_type__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Organization industry breakdown
    industry_stats = (
        Organization.objects
        .values("industry_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    context = {
        "total_orgs": Organization.objects.count(),

        "total_machines": Machine.objects.count(),

        "total_predictions": total_predictions,

        "total_high_risk": total_high_risk,

        "overall_failure_rate": overall_failure_rate,

        "risk_stats": risk_stats,

        "machine_type_stats": machine_type_stats,

        "industry_stats": industry_stats,

        "avg_probability": (
            predictions.aggregate(
                avg=Avg("failure_probability")
            )["avg"] or 0
        ),
    }

    return render(
        request,
        "ADMIN/reports.html",
        context
    )


# =========================================================
# ADMIN: DELETE ORGANIZATION
# =========================================================

def admin_delete_org(request, org_id):
    if not is_admin(request):
        return redirect("/login/")

    org = get_object_or_404(
        Organization,
        id=org_id
    )

    if request.method == "POST":
        org_name = org.organization_name
        login_user = org.login

        # Delete organization and associated records
        org.delete()

        # Delete associated login account
        login_user.delete()

        messages.success(
            request,
            f"Organization '{org_name}' deleted successfully."
        )

    return redirect("/admin-organizations/")