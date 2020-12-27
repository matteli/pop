from django.shortcuts import render
from django.db.models import Count, F, FloatField, Case, When, Sum
from django.forms.models import model_to_dict
from .models import Place, Schedule, Appointment, Config, Student
from django.contrib.sites.shortcuts import get_current_site
from django.db.models.functions import Cast
from django.views.decorators.http import require_http_methods, require_GET
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseBadRequest
import requests


def scheduling(request, config):
    places = Place.objects.all()
    schedules = {}
    days = Schedule.objects.dates("datetime", "day")
    for d in days:
        schedules[d] = Schedule.objects.filter(datetime__date=d)

    if config["max_escort"]:
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
    else:
        appointments = (
            Appointment.objects.values("place", "schedule")
            .annotate(people=Count("students"))
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
            indication = "success"
        elif a["density"] <= config["forbidden_level"]:
            indication = "secondary"
        elif a["density"] <= config["warning_level"]:
            indication = "danger"
        elif a["density"] <= config["caution_level"]:
            indication = "warning"
        else:
            indication = "success"

        app[a["place"]][a["schedule"]] = (
            a["density"] if config["show_density"] else 0.0,
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
    config = model_to_dict(
        Config.objects.get(site=get_current_site(request).id),
        exclude=["recaptcha_private"],
    )
    return render(request, "scheduling_page_view.html", scheduling(request, config))


@require_http_methods(["GET", "POST"])
def scheduling_booking(request):
    config = model_to_dict(
        Config.objects.get(site=get_current_site(request).id),
    )
    config_recaptcha_private = config.pop("recaptcha_private")

    if request.method == "GET":
        s = scheduling(request, config)
        return render(request, "scheduling_page_booking.html", s)
    elif request.method == "POST":

        # test recaptcha
        if config["recaptcha"]:
            g = request.POST["g-recaptcha-response"]
            r = requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={
                    "secret": config_recaptcha_private,
                    "response": g,
                },
            )
            j = r.json()
            if not j["success"] or j["action"] != "submit" or j["score"] < 0.5:
                return HttpResponseBadRequest()

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

        if not (0 < len(slots) <= config["max_slot"]):
            return HttpResponseBadRequest()

        student = Student()
        student.firstname = request.POST["firstname"]
        student.lastname = request.POST["lastname"]
        student.email = request.POST["email"]
        if config["max_escort"] and "escort" in request.POST:
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
            s = scheduling(request, config)
            s["errors"] = e
            return render(request, "scheduling_page_booking.html", s)

        if config["forbidden_level"]:
            with transaction.atomic():
                if config["max_escort"]:
                    apps_invalid = (
                        Appointment.objects.filter(id__in=slots)
                        .annotate(
                            density=Cast(F("place__array"), FloatField())
                            / Cast(
                                Sum("students__people") + student.people, FloatField()
                            )
                        )
                        .filter(density__lt=config["forbidden_level"])
                    )
                else:
                    apps_invalid = (
                        Appointment.objects.filter(id__in=slots)
                        .annotate(
                            density=Cast(F("place__array"), FloatField())
                            / Cast(Count("students") + 1, FloatField())
                        )
                        .filter(density__lt=config["forbidden_level"])
                    )
                if apps_invalid.count() == 0:
                    apps = Appointment.objects.filter(id__in=slots)
                    for a in apps:
                        a.students.add(student)

            if apps_invalid.count() > 0:
                s = scheduling(request, config)
                student.delete()
                s["errors"] = {
                    "message_dict": {
                        "scheduling": "Avec votre réservation, des créneaux atteignent le dernier niveau. Veillez recommencer en privilégiant des créneaux verts ou jaunes."
                    }
                }
                return render(request, "scheduling_page_booking.html", s)
        else:
            apps = Appointment.objects.filter(id__in=slots)
            for a in apps:
                a.students.add(student)
        return render(request, "booking_saved.html")