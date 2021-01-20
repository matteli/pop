from django.contrib import admin

from .models import Place, Schedule, Appointment, Student, Config


class StudentAdmin(admin.ModelAdmin):
    list_display = ("lastname", "firstname", "email", "school")


admin.site.register(Student, StudentAdmin)
admin.site.register(Schedule)
admin.site.register(Place)
admin.site.register(Appointment)
admin.site.register(Config)
