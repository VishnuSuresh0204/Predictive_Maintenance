
from django.db import models
from django.contrib.auth.models import AbstractUser

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