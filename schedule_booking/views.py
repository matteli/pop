from django.shortcuts import render
from django.db.models import Count, F, FloatField, Case, When, Sum
from .models import Place, Schedule, Appointment, Config, Student
from django.contrib.sites.shortcuts import get_current_site
from django.db.models.functions import Cast
from django.views.decorators.http import require_http_methods, require_GET
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseBadRequest


def get_option(request, option):
    return getattr(Config.objects.get(site=get_current_site(request).id), option)


def scheduling(request):
    places = Place.objects.all()
    schedules = {}
    days = Schedule.objects.dates("datetime", "day")
    config = {
        "level": {
            "correct": (0.0, "success"),
            "caution": (get_option(request, "caution_level"), "warning"),
            "warning": (get_option(request, "warning_level"), "danger"),
            "forbidden": (get_option(request, "forbidden_level"), "secondary"),
        },
        "max_escort": get_option(request, "max_escort"),
        "max_slot": get_option(request, "max_slot"),
    }

    for d in days:
        schedules[d] = Schedule.objects.filter(datetime__date=d)
    appointments = (
        Appointment.objects.values("place", "schedule")
        .annotate(people=Sum("students__people"))
        .annotate(
            density=Case(
                When(people=0, then=-1.0),
                default=Cast(F("place__array"), FloatField())
                / Cast(F("people") + 1, FloatField()),
            )
        )
    )

    app = {}
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

        app[a["place"]][a["schedule"]] = (
            a["density"] if get_option(request, "show_density") else 0.0,
            indication,
        )

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
        slots = []
        for k, v in request.POST.items():
            if k.endswith("slot") and v == "on":
                try:
                    slot = list(map(int, k.split("-")[:2]))  # [Place__id, Schedule__id]
                except:
                    return HttpResponseBadRequest()
                else:
                    if (
                        Place.objects.filter(id=slot[0]).count() > 0
                        and Schedule.objects.filter(id=slot[1]).count() > 0
                    ):
                        slots.append("-".join(list(map(str, slot))))

        if not (0 < len(slots) <= get_option(request, "max_slot")):
            return HttpResponseBadRequest()

        student = Student()
        student.firstname = request.POST["firstname"]
        student.lastname = request.POST["lastname"]
        student.email = request.POST["email"]
        if "escort" in request.POST:
            try:
                student.people = int(request.POST["escort"]) + 1
            except:
                return HttpResponseBadRequest()
        else:
            student.people = 1

        try:
            student.full_clean()
            student.save()

        except ValidationError as e:
            s = scheduling(request)
            s["errors"] = e
            return render(request, "scheduling_page_booking.html", s)

        forbidden = get_option(request, "forbidden_level")
        with transaction.atomic():
            apps_invalid = (
                Appointment.objects.filter(id__in=slots)
                .annotate(
                    density=Cast(F("place__array"), FloatField())
                    / Cast(Sum("students__people") + student.people, FloatField())
                )
                .filter(density__lt=forbidden)
            )
            if apps_invalid.count() == 0:
                apps = Appointment.objects.filter(id__in=slots)
                for a in apps:
                    a.students.add(student)

        if apps_invalid.count() > 0:
            s = scheduling(request)
            student.delete()
            s["errors"] = {
                "message_dict": {
                    "scheduling": "Avec votre réservation, des créneaux atteignent le dernier niveau. Veillez recommencer en privilégiant des créneaux verts ou jaunes."
                }
            }
            return render(request, "scheduling_page_booking.html", s)
        return render(request, "booking_saved.html")