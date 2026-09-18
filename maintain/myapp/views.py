from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Avg, Count
from django.utils import timezone

from .models import *
from .ml.predictor import predict_failure

def get_current_org(request):
    """Helper to safely retrieve the logged in organization, or None."""
    if not request.user.is_authenticated:
        return None
    return Organization.objects.filter(login=request.user).first()


def is_admin(request):
    return request.user.is_authenticated and (
        request.user.usertype == "Admin" or request.user.is_superuser
    )


def get_thresholds(org):
    """Return the (warning, high_risk) probability bands for an organization."""
    threshold = RiskThreshold.objects.filter(organization=org).order_by("-year").first()
    if threshold:
        return threshold.warning_threshold, threshold.high_risk_threshold
    return 0.30, 0.70


def home(request):
    features = [
        {"icon": "📡", "title": "Sensor Data Logging", "desc": "Record temperature, vibration, pressure, torque and load readings from every machine."},
        {"icon": "🤖", "title": "AI Failure Prediction", "desc": "A trained classification model estimates the probability of an upcoming breakdown."},
        {"icon": "⚠️", "title": "Risk Alerts", "desc": "Machines are graded Normal, Warning or High Risk so teams act before a failure happens."},
        {"icon": "🛠️", "title": "Maintenance History", "desc": "Every inspection and repair is logged with technician, cost and downtime for auditing."},
    ]
    return render(request, "home.html", {"features": features})


def org_home(request):
    if not request.user.is_authenticated:
        return redirect("/login/")

    org = get_current_org(request)
    if not org:
        if request.user.usertype == "Admin":
            return redirect("/admin-home/")
        messages.error(request, "Organization profile not found.")
        return redirect("/login/")

    machines = Machine.objects.filter(organization=org).select_related("machine_type")
    recent_predictions = (
        Prediction.objects.filter(organization=org)
        .select_related("machine")
        .order_by("-prediction_date")[:5]
    )
    open_alerts = Alert.objects.filter(organization=org, status="Open").select_related("machine")

    total_predictions = Prediction.objects.filter(organization=org).count()
    high_risk_count = Prediction.objects.filter(organization=org, risk_level="High Risk").count()
    failure_rate = round((high_risk_count / total_predictions) * 100, 2) if total_predictions else 0.0

    context = {
        "org": org,
        "machines": machines,
        "recent_predictions": recent_predictions,
        "open_alerts": open_alerts,
        "total_machines": machines.count(),
        "operational_count": machines.filter(status="Operational").count(),
        "total_predictions": total_predictions,
        "high_risk_count": high_risk_count,
        "failure_rate": failure_rate,
        "open_alert_count": open_alerts.count(),
    }
    return render(request, "ORGANIZATION/home.html", context)


def admin_home(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    if not is_admin(request):
        messages.error(request, "Admin clearance required.")
        return redirect("/org-home/")

    organizations = Organization.objects.all().order_by("-created_at")
    open_alerts = (
        Alert.objects.filter(status="Open")
        .select_related("machine", "organization")
        .order_by("-created_at")
    )
    all_predictions = Prediction.objects.all()
    scheduled_maintenance = MaintenanceRecord.objects.filter(
        status__in=["Scheduled", "In Progress"]
    ).select_related("machine", "organization")

    context = {
        "organizations": organizations,
        "open_alerts": open_alerts,
        "scheduled_maintenance": scheduled_maintenance,
        "total_machines_sum": Machine.objects.count(),
        "total_predictions_sum": all_predictions.count(),
        "total_high_risk_sum": all_predictions.filter(risk_level="High Risk").count(),
        "total_orgs_count": organizations.count(),
        "open_alert_count": open_alerts.count(),
    }
    return render(request, "ADMIN/home.html", context)


def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        organization_name = request.POST.get("organization_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        industry_type = request.POST.get("industry_type", "").strip()

        if Login.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose a different handle.")
            return render(request, "register.html")

        user = Login.objects.create_user(
            username=username,
            password=password,
            usertype="Organization",
        )

        Organization.objects.create(
            login=user,
            organization_name=organization_name,
            email=email,
            phone=phone,
            address=address,
            industry_type=industry_type,
        )

        messages.success(request, "Organization registered successfully. Please log in to register your machines.")
        return redirect("/login/")

    return render(request, "register.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            if user.usertype == "Admin" or user.is_superuser:
                return redirect("/admin-home/")
            return redirect("/org-home/")

        messages.error(request, "Invalid username or password credentials.")
        return render(request, "login.html")

    return render(request, "login.html")


def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have been securely logged out.")
    return redirect("/login/")


# ---------------------------------------------------------------------
# ORGANIZATION PROFILE
# ---------------------------------------------------------------------

def profile(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    if request.method == "POST":
        org.organization_name = request.POST.get("organization_name", org.organization_name)
        org.email = request.POST.get("email", org.email)
        org.phone = request.POST.get("phone", org.phone)
        org.address = request.POST.get("address", org.address)
        org.industry_type = request.POST.get("industry_type", org.industry_type)
        org.save()
        messages.success(request, "Organization profile successfully updated.")
        return redirect("/profile/")

    total_machines = Machine.objects.filter(organization=org).count()
    return render(request, "ORGANIZATION/profile.html", {"org": org, "total_machines": total_machines})


# ---------------------------------------------------------------------
# MACHINE MANAGEMENT MODULE
# ---------------------------------------------------------------------

def register_machine(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    if request.method == "POST":
        serial_number = request.POST.get("serial_number", "").strip()

        if Machine.objects.filter(serial_number=serial_number).exists():
            messages.error(request, "A machine with that serial number is already registered.")
            return redirect("/register-machine/")

        try:
            operating_hours = float(request.POST.get("operating_hours", 0) or 0)
        except ValueError:
            messages.error(request, "Operating hours must be a number.")
            return redirect("/register-machine/")

        machine = Machine.objects.create(
            organization=org,
            machine_name=request.POST.get("machine_name", "").strip(),
            machine_type_id=request.POST.get("machine_type_id") or None,
            serial_number=serial_number,
            manufacturer=request.POST.get("manufacturer", "").strip(),
            location=request.POST.get("location", "").strip(),
            installation_date=request.POST.get("installation_date"),
            operating_hours=operating_hours,
            status=request.POST.get("status", "Operational"),
        )

        messages.success(request, f"Machine '{machine.machine_name}' registered successfully.")
        return redirect("/machines/")

    machine_types = MachineType.objects.all()
    return render(request, "ORGANIZATION/register_machine.html", {"org": org, "machine_types": machine_types})


def machine_list(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    machines = (
        Machine.objects.filter(organization=org)
        .select_related("machine_type")
        .order_by("machine_name")
    )

    machine_data = []
    for machine in machines:
        machine_data.append({
            "machine": machine,
            "latest_prediction": machine.latest_prediction,
            "latest_reading": machine.latest_reading,
            "reading_count": machine.sensordata_set.count(),
        })

    context = {
        "org": org,
        "machine_data": machine_data,
        "total_machines": machines.count(),
        "operational_count": machines.filter(status="Operational").count(),
        "maintenance_count": machines.filter(status="Under Maintenance").count(),
        "stopped_count": machines.filter(status="Stopped").count(),
    }
    return render(request, "ORGANIZATION/machine_list.html", context)


def machine_detail(request, machine_id):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    machine = get_object_or_404(Machine, id=machine_id, organization=org)
    readings = SensorData.objects.filter(machine=machine).order_by("-recorded_at")[:20]
    predictions = Prediction.objects.filter(machine=machine).order_by("-prediction_date")[:10]
    maintenance = MaintenanceRecord.objects.filter(machine=machine).order_by("-maintenance_date")
    alerts = Alert.objects.filter(machine=machine).order_by("-created_at")[:10]

    averages = SensorData.objects.filter(machine=machine).aggregate(
        avg_temperature=Avg("temperature"),
        avg_vibration=Avg("vibration"),
        avg_pressure=Avg("pressure"),
        avg_torque=Avg("torque"),
    )

    context = {
        "org": org,
        "machine": machine,
        "readings": readings,
        "predictions": predictions,
        "maintenance": maintenance,
        "alerts": alerts,
        "averages": averages,
        "latest_prediction": machine.latest_prediction,
    }
    return render(request, "ORGANIZATION/machine_detail.html", context)


def edit_machine(request, machine_id):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    machine = get_object_or_404(Machine, id=machine_id, organization=org)

    if request.method == "POST":
        machine.machine_name = request.POST.get("machine_name", machine.machine_name)
        machine.manufacturer = request.POST.get("manufacturer", machine.manufacturer)
        machine.location = request.POST.get("location", machine.location)
        machine.status = request.POST.get("status", machine.status)
        machine_type_id = request.POST.get("machine_type_id")
        if machine_type_id:
            machine.machine_type_id = machine_type_id
        try:
            machine.operating_hours = float(request.POST.get("operating_hours", machine.operating_hours))
        except ValueError:
            messages.error(request, "Operating hours must be a number.")
            return redirect(f"/edit-machine/{machine.id}/")
        machine.save()

        messages.success(request, f"Machine '{machine.machine_name}' updated.")
        return redirect(f"/machine/{machine.id}/")

    machine_types = MachineType.objects.all()
    return render(request, "ORGANIZATION/edit_machine.html", {"org": org, "machine": machine, "machine_types": machine_types})


def delete_machine(request, machine_id):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    machine = get_object_or_404(Machine, id=machine_id, organization=org)
    machine_name = machine.machine_name
    machine.delete()

    messages.success(request, f"Machine '{machine_name}' and all associated records deleted.")
    return redirect("/machines/")


# ---------------------------------------------------------------------
# SENSOR DATA + AI PREDICTION MODULE
# ---------------------------------------------------------------------

def add_sensor_data(request):
    """
    Operator enters a set of live readings for a machine. The reading is
    saved and immediately passed to the trained model, which produces a
    Prediction and, if the risk is elevated, an Alert.
    """
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    machines = Machine.objects.filter(organization=org).exclude(status="Decommissioned")

    if request.method == "POST":
        machine_id = request.POST.get("machine_id")
        machine = get_object_or_404(Machine, id=machine_id, organization=org)

        numeric_fields = [
            "temperature", "vibration", "pressure",
            "rotational_speed", "torque", "power_consumption", "operating_hours",
        ]
        values = {}
        try:
            for field in numeric_fields:
                values[field] = float(request.POST.get(field, 0) or 0)
        except ValueError:
            messages.error(request, "All sensor readings must be valid numbers.")
            return render(request, "ORGANIZATION/add_sensor_data.html", {"org": org, "machines": machines})

        reading = SensorData.objects.create(machine=machine, **values)

        # Keep the machine's cumulative hours in sync with the latest reading
        if values["operating_hours"] > machine.operating_hours:
            machine.operating_hours = values["operating_hours"]
            machine.save()

        warning, high_risk = get_thresholds(org)
        features = dict(values)
        features["machine_age"] = machine.age_in_years

        try:
            result = predict_failure(features, warning=warning, high_risk=high_risk)
        except FileNotFoundError:
            messages.warning(request, f"Reading #{reading.id} saved, but the prediction model is not available yet.")
            return redirect(f"/machine/{machine.id}/")

        prediction = Prediction.objects.create(
            machine=machine,
            organization=org,
            sensor_data=reading,
            failure_probability=result["failure_probability"],
            risk_level=result["risk_level"],
            predicted_failure=result["predicted_failure"],
            recommended_action=result["recommended_action"],
            top_factors=result["top_factors"],
            model_version=result["model_version"],
            processing_time_ms=result["processing_time_ms"],
        )

        if prediction.risk_level in ["Warning", "High Risk"]:
            Alert.objects.create(
                machine=machine,
                organization=org,
                prediction=prediction,
                severity=prediction.risk_level,
                message=(
                    f"{machine.machine_name} flagged as {prediction.risk_level} with a "
                    f"{prediction.probability_percent}% failure probability. "
                    f"{prediction.recommended_action}"
                ),
            )

        messages.success(
            request,
            f"Reading logged. {machine.machine_name} assessed as {prediction.risk_level} "
            f"({prediction.probability_percent}% failure probability).",
        )
        return redirect(f"/prediction/{prediction.id}/")

    return render(request, "ORGANIZATION/add_sensor_data.html", {"org": org, "machines": machines})


def prediction_detail(request, prediction_id):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    prediction = get_object_or_404(
        Prediction.objects.select_related("machine", "sensor_data"),
        id=prediction_id,
        organization=org,
    )
    return render(request, "ORGANIZATION/prediction_detail.html", {"org": org, "prediction": prediction})


def prediction_history(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    predictions = (
        Prediction.objects.filter(organization=org)
        .select_related("machine", "sensor_data")
        .order_by("-prediction_date")
    )

    machine_id = request.GET.get("machine_id")
    if machine_id:
        predictions = predictions.filter(machine_id=machine_id)

    context = {
        "org": org,
        "predictions": predictions,
        "machines": Machine.objects.filter(organization=org),
        "selected_machine_id": machine_id,
        "total_predictions": predictions.count(),
        "normal_count": predictions.filter(risk_level="Normal").count(),
        "warning_count": predictions.filter(risk_level="Warning").count(),
        "high_risk_count": predictions.filter(risk_level="High Risk").count(),
    }
    return render(request, "ORGANIZATION/prediction_history.html", context)


def alerts_view(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    if request.method == "POST":
        alert = get_object_or_404(Alert, id=request.POST.get("alert_id"), organization=org)
        action = request.POST.get("action")
        if action == "acknowledge":
            alert.status = "Acknowledged"
        elif action == "resolve":
            alert.status = "Resolved"
            alert.resolved_at = timezone.now()
        alert.save()
        messages.success(request, f"Alert #{alert.id} marked as {alert.status}.")
        return redirect("/alerts/")

    alerts = Alert.objects.filter(organization=org).select_related("machine", "prediction")
    context = {
        "org": org,
        "alerts": alerts,
        "open_count": alerts.filter(status="Open").count(),
        "acknowledged_count": alerts.filter(status="Acknowledged").count(),
        "resolved_count": alerts.filter(status="Resolved").count(),
    }
    return render(request, "ORGANIZATION/alerts.html", context)


# ---------------------------------------------------------------------
# MAINTENANCE MODULE
# ---------------------------------------------------------------------

def add_maintenance(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    if request.method == "POST":
        machine = get_object_or_404(Machine, id=request.POST.get("machine_id"), organization=org)

        cost = request.POST.get("cost")
        downtime = request.POST.get("downtime_hours")
        try:
            cost = float(cost) if cost else None
            downtime = float(downtime) if downtime else None
        except ValueError:
            messages.error(request, "Cost and downtime must be numeric values.")
            return redirect("/add-maintenance/")

        record = MaintenanceRecord.objects.create(
            machine=machine,
            organization=org,
            triggered_by_id=request.POST.get("prediction_id") or None,
            maintenance_type=request.POST.get("maintenance_type", "Preventive"),
            description=request.POST.get("description", "").strip(),
            technician=request.POST.get("technician", "").strip(),
            cost=cost,
            downtime_hours=downtime,
            maintenance_date=request.POST.get("maintenance_date"),
            status=request.POST.get("status", "Scheduled"),
        )

        if record.status in ["Scheduled", "In Progress"]:
            machine.status = "Under Maintenance"
            machine.save()

        messages.success(request, f"Maintenance record #{record.id} created for '{machine.machine_name}'.")
        return redirect("/maintenance-history/")

    machines = Machine.objects.filter(organization=org)
    return render(request, "ORGANIZATION/add_maintenance.html", {"org": org, "machines": machines})


def maintenance_history(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    records = (
        MaintenanceRecord.objects.filter(organization=org)
        .select_related("machine")
        .order_by("-maintenance_date")
    )

    context = {
        "org": org,
        "records": records,
        "total_records": records.count(),
        "scheduled_count": records.filter(status="Scheduled").count(),
        "completed_count": records.filter(status="Completed").count(),
        "total_cost": sum(r.cost for r in records if r.cost) or 0,
        "total_downtime": sum(r.downtime_hours for r in records if r.downtime_hours) or 0,
    }
    return render(request, "ORGANIZATION/maintenance_history.html", context)


def update_maintenance_status(request, record_id):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    record = get_object_or_404(MaintenanceRecord, id=record_id, organization=org)

    if request.method == "POST":
        record.status = request.POST.get("status", record.status)
        record.save()

        if record.status == "Completed":
            record.machine.status = "Operational"
            record.machine.save()

        messages.success(request, f"Maintenance record #{record.id} marked as {record.status}.")

    return redirect(request.META.get("HTTP_REFERER", "/maintenance-history/"))


# ---------------------------------------------------------------------
# ADMIN MODULE
# ---------------------------------------------------------------------

def admin_machines(request):
    if not is_admin(request):
        messages.error(request, "Admin access required.")
        return redirect("/login/")

    machines = (
        Machine.objects.all()
        .select_related("organization", "machine_type")
        .order_by("-registered_at")
    )

    machine_data = []
    for machine in machines:
        machine_data.append({
            "machine": machine,
            "latest_prediction": machine.latest_prediction,
            "prediction_count": machine.prediction_set.count(),
        })

    context = {
        "machine_data": machine_data,
        "organizations": Organization.objects.all(),
        "total_machines": machines.count(),
        "operational_count": machines.filter(status="Operational").count(),
        "maintenance_count": machines.filter(status="Under Maintenance").count(),
    }
    return render(request, "ADMIN/machines.html", context)


def admin_predictions(request):
    if not is_admin(request):
        messages.error(request, "Admin access required.")
        return redirect("/login/")

    predictions = (
        Prediction.objects.all()
        .select_related("machine", "organization", "sensor_data")
        .order_by("-prediction_date")
    )

    context = {
        "predictions": predictions,
        "organizations": Organization.objects.all(),
        "normal_results": predictions.filter(risk_level="Normal"),
        "warning_results": predictions.filter(risk_level="Warning"),
        "high_risk_results": predictions.filter(risk_level="High Risk"),
    }
    return render(request, "ADMIN/predictions.html", context)


def admin_alerts(request):
    if not is_admin(request):
        messages.error(request, "Admin access required.")
        return redirect("/login/")

    if request.method == "POST":
        alert = get_object_or_404(Alert, id=request.POST.get("alert_id"))
        action = request.POST.get("action")
        if action == "acknowledge":
            alert.status = "Acknowledged"
        elif action == "resolve":
            alert.status = "Resolved"
            alert.resolved_at = timezone.now()
        alert.save()
        messages.success(request, f"Alert #{alert.id} for '{alert.machine.machine_name}' marked as {alert.status}.")
        return redirect(request.META.get("HTTP_REFERER", "/admin-alerts/"))

    alerts = Alert.objects.all().select_related("machine", "organization", "prediction")
    context = {
        "alerts": alerts,
        "open_count": alerts.filter(status="Open").count(),
        "high_severity_count": alerts.filter(severity="High Risk", status="Open").count(),
    }
    return render(request, "ADMIN/alerts.html", context)


def set_risk_threshold(request):
    if not is_admin(request):
        messages.error(request, "Admin access required.")
        return redirect("/login/")

    if request.method == "POST":
        org_id = request.POST.get("org_id")
        try:
            year = int(request.POST.get("year", timezone.now().year))
            warning = float(request.POST.get("warning_threshold", 0.30))
            high_risk = float(request.POST.get("high_risk_threshold", 0.70))
        except ValueError:
            messages.error(request, "Please enter valid numeric values for year and thresholds.")
            return redirect("/admin-home/")

        if not (0 <= warning < high_risk <= 1):
            messages.error(request, "Thresholds must satisfy 0 <= warning < high risk <= 1.")
            return redirect(request.META.get("HTTP_REFERER", "/admin-home/"))

        org = get_object_or_404(Organization, id=org_id)

        threshold_obj, created = RiskThreshold.objects.get_or_create(
            organization=org,
            year=year,
            defaults={"warning_threshold": warning, "high_risk_threshold": high_risk},
        )
        if not created:
            threshold_obj.warning_threshold = warning
            threshold_obj.high_risk_threshold = high_risk
            threshold_obj.save()

        messages.success(
            request,
            f"Risk bands set for '{org.organization_name}' ({year}): "
            f"Warning at {warning}, High Risk at {high_risk}.",
        )
        return redirect(request.META.get("HTTP_REFERER", "/admin-home/"))

    return redirect("/admin-home/")


def admin_organizations(request):
    if not is_admin(request):
        return redirect("/login/")

    organizations = Organization.objects.all().order_by("-created_at")
    org_data = []
    for org in organizations:
        machine_count = Machine.objects.filter(organization=org).count()
        prediction_count = Prediction.objects.filter(organization=org).count()
        high_risk_count = Prediction.objects.filter(organization=org, risk_level="High Risk").count()
        failure_rate = round((high_risk_count / prediction_count) * 100, 2) if prediction_count else 0.0
        threshold_obj = RiskThreshold.objects.filter(organization=org).order_by("-year").first()
        org_data.append({
            "org": org,
            "machine_count": machine_count,
            "prediction_count": prediction_count,
            "high_risk_count": high_risk_count,
            "failure_rate": failure_rate,
            "warning_threshold": threshold_obj.warning_threshold if threshold_obj else None,
            "high_risk_threshold": threshold_obj.high_risk_threshold if threshold_obj else None,
            "threshold_year": threshold_obj.year if threshold_obj else None,
        })

    return render(request, "ADMIN/organizations.html", {"org_data": org_data, "total_count": organizations.count()})


def admin_maintenance(request):
    if not is_admin(request):
        return redirect("/login/")

    records = (
        MaintenanceRecord.objects.all()
        .select_related("machine", "organization")
        .order_by("-maintenance_date")
    )

    context = {
        "records": records,
        "scheduled_records": records.filter(status="Scheduled"),
        "in_progress_records": records.filter(status="In Progress"),
        "completed_records": records.filter(status="Completed"),
    }
    return render(request, "ADMIN/maintenance.html", context)


def admin_reports(request):
    if not is_admin(request):
        return redirect("/login/")

    all_predictions = Prediction.objects.all()
    total_predictions = all_predictions.count()
    total_high_risk = all_predictions.filter(risk_level="High Risk").count()
    overall_failure_rate = round((total_high_risk / total_predictions) * 100, 2) if total_predictions else 0.0

    # Risk level breakdown
    risk_stats = (
        all_predictions.values("risk_level")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Which machine types fail most often
    machine_type_stats = (
        all_predictions.filter(risk_level="High Risk", machine__machine_type__isnull=False)
        .values("machine__machine_type__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Maintenance breakdown
    maintenance_stats = (
        MaintenanceRecord.objects.values("maintenance_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Sector breakdown
    industry_stats = (
        Organization.objects.values("industry_type")
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
        "maintenance_stats": maintenance_stats,
        "industry_stats": industry_stats,
        "avg_probability": all_predictions.aggregate(avg=Avg("failure_probability"))["avg"] or 0,
    }
    return render(request, "ADMIN/reports.html", context)


def admin_delete_org(request, org_id):
    if not is_admin(request):
        return redirect("/login/")

    org = get_object_or_404(Organization, id=org_id)
    org_name = org.organization_name
    login_user = org.login
    org.delete()
    if login_user:
        login_user.delete()

    messages.success(request, f"Organization '{org_name}' and associated credentials deleted.")
    return redirect("/admin-organizations/")