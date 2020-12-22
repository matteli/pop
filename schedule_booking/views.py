from django.shortcuts import render
from django.db.models import Count, F, FloatField, Case, When
from .models import Place, Schedule, Appointment, Config, Student
from django.contrib.sites.shortcuts import get_current_site
from django.db.models.functions import Cast
from django.views.decorators.http import require_http_methods, require_GET
from django.core.exceptions import ValidationError


def get_option(request, option):
    return getattr(Config.objects.get(site=get_current_site(request).id), option)


def scheduling(request):
    places = Place.objects.all()
    schedules = {}
    days = Schedule.objects.dates("datetime", "day")
    for d in days:
        schedules[d] = Schedule.objects.filter(datetime__date=d)
    if get_option(request, "group"):
        appointments = (
            Appointment.objects.values("place", "schedule")
            .annotate(people=Count("students"))
            .annotate(
                density=Case(
                    When(people=0, then=-1.0),
                    default=Cast(F("place__array"), FloatField())
                    / Cast(F("people"), FloatField()),
                )
            )
        )
    else:
        appointments = (
            Appointment.objects.values("place", "schedule")
            .annotate(people=Count("students__people"))
            .annotate(
                density=Case(
                    When(people=0, then=-1.0),
                    default=Cast(F("place__array"), FloatField())
                    / Cast(F("people"), FloatField()),
                )
            )
        )

    app = {}
    config = {
        "level": {
            "correct": (0.0, "success"),
            "caution": (get_option(request, "caution_level"), "warning"),
            "warning": (get_option(request, "warning_level"), "danger"),
            "forbidden": (get_option(request, "forbidden_level"), "secondary"),
        },
        "group": get_option(request, "group"),
    }
    for a in appointments:
        if a["place"] not in app:
            app[a["place"]] = {}
        if a["density"] < 0:
            indication = config["level"]["correct"][1]
        elif a["density"] <= config["level"]["forbidden"][0]:
            indication = config["level"]["forbidden"][1]
        elif a["density"] <= config["level"]["warning"][0]:
            indication = config["level"]["warning"][1]
        elif a["density"] <= config["level"]["caution"][0]:
            indication = config["level"]["caution"][1]
        else:
            indication = config["level"]["correct"][1]

        app[a["place"]][a["schedule"]] = (a["density"], indication)

    return {
        "places": places,
        "schedules": schedules,
        "days": days,
        "app": app,
        "config": config,
    }


@require_GET
def scheduling_view(request):
    return render(request, "scheduling_page_view.html", scheduling(request))


@require_http_methods(["GET", "POST"])
def scheduling_booking(request):
    if request.method == "GET":
        s = scheduling(request)
        return render(request, "scheduling_page_booking.html", s)
    elif request.method == "POST":
        student = Student()
        student.firstname = request.POST["firstname"]
        student.lastname = request.POST["lastname"]
        student.email = request.POST["email"]

        try:
            student.full_clean()
            student.save()

        except ValidationError as e:
            s = scheduling(request)
            s["errors"] = e
            return render(request, "scheduling_page_booking.html", s)

        return render(request, "booking_saved.html")
