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
from django.core.mail import EmailMessage
import requests
from pop import settings


def scheduling(request, config):
    places = Place.objects.all()
    schools = Student.SCHOOLS_CHOICE
    schedules = {}
    days = Schedule.objects.dates("datetime", "day")
    for d in days:
        schedules[d] = Schedule.objects.filter(datetime__date=d)

    if config["max_escort"]:
        appointments = (
            Appointment.objects.values("place", "schedule")
            .annotate(stu=Count("students"))
            .annotate(people=Case(When(stu=0, then=0), default=Sum("students__people")))
            .annotate(rate=100 * F("people") / F("place__gauge"))
        )

    else:
        appointments = (
            Appointment.objects.values("place", "schedule")
            .annotate(people=Count("students"))
            .annotate(rate=100 * F("people") / F("place__gauge"))
        )

    app = {}
    for a in appointments:
        if a["place"] not in app:
            app[a["place"]] = {}
        if a["rate"] >= config["forbidden_level"]:
            indication = "secondary"
        elif a["rate"] >= config["warning_level"]:
            indication = "danger"
        elif a["rate"] >= config["caution_level"]:
            indication = "warning"
        else:
            indication = "success"

        app[a["place"]][a["schedule"]] = (
            a["people"] if config["show_people"] else -1,
            indication,
        )

    return {
        "places": places,
        "schedules": schedules,
        "days": days,
        "app": app,
        "schools": schools,
        "config": config,
    }


def body_email(apps):
    r = "\n"
    s = (
        f"Nous vous confirmons que votre inscription aux portes ouvertes du lycée Aristide Briand est validée.\n\n"
        f"Vous êtes attendus :\n"
        f"""{r.join(f"- le {a['schedule__datetime'].strftime('%A %d/%m')} à {a['schedule__datetime'].strftime('%H:%M')} pour visiter l'emplacement {a['place__name']}"for a in apps)}"""
        f"\n\n"
        f"Le port du masque est obligatoire sur toute la cité scolaire. L'élève doit être accompagné par un seul adulte référent."
        f"\n\n"
        f"Le lycée Aristide Briand"
        f"\n\n"
        f"Ne répondez pas à cet email. Si vous voulez contacter le lycée Aristide Briand, utilisez l'adresse mail suivante : ce.0440069l@ac-nantes.fr."
    )
    return s


def body_email_test(apps):
    r = "\n"
    s = (
        f"Nous vous confirmons que le test de votre inscription aux portes ouvertes du lycée Aristide Briand est réussi.\n\n"
        f"Vous n'êtes pas encore attendus :\n"
        f"""{r.join(f"- le {a['schedule__datetime'].strftime('%A %d/%m')} à {a['schedule__datetime'].strftime('%H:%M')} pour visiter l'emplacement {a['place__name']}"for a in apps)}"""
        f"\n\n"
        f"Le port du masque est obligatoire sur toute la cité scolaire. L'élève doit être accompagné par un seul adulte référent."
        f"\n\n"
        f"Le lycée Aristide Briand"
        f"\n\n"
        f"Ne répondez pas à cet email. Si vous voulez contacter le lycée Aristide Briand, utilisez l'adresse mail suivante : ce.0440069l@ac-nantes.fr."
    )
    return s


@require_GET
def scheduling_view(request):
    config = model_to_dict(
        Config.objects.get(site=get_current_site(request).id),
        exclude=["recaptcha_private", "send_email_confirmation"],
    )
    return render(request, "scheduling_page_view.html", scheduling(request, config))


@require_http_methods(["GET", "POST"])
def scheduling_booking(request):
    config = model_to_dict(
        Config.objects.get(site=get_current_site(request).id),
    )
    config_recaptcha_private = config.pop("recaptcha_private")
    config_send_email_confirmation = config.pop("send_email_confirmation")

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

        student = Student()
        student.firstname = request.POST["firstname"]
        student.lastname = request.POST["lastname"]
        student.email = request.POST["email"]
        student.school = request.POST["school"]
        if config["max_escort"] and "escort" in request.POST:
            try:
                student.people = int(request.POST["escort"]) + 1
            except:
                return HttpResponseBadRequest()
        else:
            student.people = 1

        slots = []
        places = []
        schedules = []
        for k, v in request.POST.items():
            if k.endswith("slot") and v != "0":
                try:
                    slot = list(map(int, v.split("-")))  # [Place__id, Schedule__id]
                except:
                    return HttpResponseBadRequest()
                else:
                    if (
                        Place.objects.filter(id=slot[0]).count() > 0
                        and Schedule.objects.filter(id=slot[1]).count() > 0
                    ):
                        if not slot[0] in places and not slot[1] in schedules:
                            schedule = Schedule.objects.filter(id=slot[1]).first()
                            if schedule:
                                authorizeds = schedule.authorizeds.split(" ")
                                if student.school[:2] not in authorizeds:
                                    return HttpResponseBadRequest()
                            places.append(slot[0])
                            schedules.append(slot[1])
                            slots.append("-".join(list(map(str, slot))))

        if not (0 < len(slots) <= config["max_slot"]):
            return HttpResponseBadRequest()

        try:
            student.full_clean()
            student.save()

        except ValidationError as e:
            s = scheduling(request, config)
            s["errors"] = e
            return render(request, "scheduling_page_booking.html", s)

        if config["forbidden_level"]:
            ok = True
            with transaction.atomic():
                if config["max_escort"]:
                    apps = (
                        Appointment.objects.filter(id__in=slots)
                        .annotate(stu=Count("students"))
                        .annotate(
                            people=Case(
                                When(stu=0, then=0), default=Sum("students__people")
                            )
                        )
                    )
                else:
                    apps = Appointment.objects.filter(id__in=slots).annotate(
                        people=Count("students")
                    )
                for a in apps:
                    if a.people + student.people > a.place.gauge:
                        ok = False
                        break
                if ok:
                    for a in apps:
                        a.students.add(student)

            if not ok:
                s = scheduling(request, config)
                student.delete()
                s["errors"] = {
                    "message_dict": {
                        "scheduling": "Des créneaux se sont remplis avant que votre inscription soit validée. Veuillez recommencer avec d'autres créneaux."
                    }
                }
                return render(request, "scheduling_page_booking.html", s)
        else:
            apps = Appointment.objects.filter(id__in=slots)
            for a in apps:
                a.students.add(student)

        apps_dict = apps.values("place__name", "schedule__datetime")
        if config_send_email_confirmation:
            email = EmailMessage(
                "Inscription aux portes ouvertes du lycée Aristide Briand",
                body_email(apps_dict)
                if not config["beta_test"]
                else body_email_test(apps_dict),
                settings.DEFAULT_FROM_EMAIL,
                [student.email],
            )
            email.send()
        context = {"apps": apps_dict}
        return render(request, "booking_saved.html", context)