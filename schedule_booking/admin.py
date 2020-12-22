from django.contrib import admin

from .models import Place, Schedule, Appointment, Student, Config

admin.site.register([Place, Schedule, Appointment, Student, Config])