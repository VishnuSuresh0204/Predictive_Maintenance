from django.contrib import admin
from django.urls import path
from myapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home),
    path('admin-home/', views.admin_home),
    path('org-home/', views.org_home),
    path('register/', views.register),
    path('login/', views.login_view),
    path('logout/', views.logout_view),

    path('profile/', views.profile),

    # Machine Management
    path('machines/', views.machine_list),
    path('machine/<int:machine_id>/', views.machine_detail),
    path('add-machine/', views.register_machine),
    path('edit-machine/<int:machine_id>/', views.edit_machine),
    path('delete-machine/<int:machine_id>/', views.delete_machine),

    # Sensor Data & AI Prediction
    path('add-sensor-data/', views.add_sensor_data),
    path('add-sensor-data/<int:machine_id>/', views.add_sensor_data),
    path('prediction/<int:prediction_id>/', views.prediction_detail),
    path('prediction-history/', views.prediction_history),

    # Admin Management
    path('admin-organizations/', views.admin_organizations),
    path('admin-delete-org/<int:org_id>/', views.admin_delete_org),
    path('admin-machines/', views.admin_machines),
    path('admin-predictions/', views.admin_predictions),
    path('admin-reports/', views.admin_reports),
]