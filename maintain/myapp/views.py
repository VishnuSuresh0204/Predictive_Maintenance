from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from .models import *
# Create your views here.

def home(request):
    return render(request, "home.html")

def admin_home(request):
    return render(request, "ADMIN/home.html")

def org_home(request):
    return render(request, "ORGANIZATION/home.html")

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
 