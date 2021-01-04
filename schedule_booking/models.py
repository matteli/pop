from django.db import models
from django.contrib.sites.models import Site
from django.core.validators import MaxValueValidator, MinValueValidator


class Config(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE)
    max_escort = models.PositiveIntegerField(
        default=0,
        help_text="Nombre maximal d'accompagnateurs. La valeur à 0 enlève la demande de cette information.",
    )
    max_slot = models.PositiveIntegerField(
        default=2,
        help_text="Nombre maximal de créneaux sélectionnable par inscription.",
    )
    show_people = models.BooleanField(
        default=True,
        help_text="Montrer le nombre de persone ou de groupe de personnes.",
    )
    caution_level = models.FloatField(
        default=8,
        help_text="Surface en-dessous de laquelle le créneau passe en orange. Si 0, le niveau n'est pas utilisé.",
    )
    warning_level = models.FloatField(
        default=4,
        help_text="Surface en-dessous de laquelle le créneau passe en rouge. Si 0, le niveau n'est pas utilisé.",
    )
    forbidden_level = models.FloatField(
        default=3,
        help_text="Surface en-dessous de laquelle le créneau n'est plus sélectionnable. Si 0, le niveau n'est pas utilisé.",
    )
    recaptcha = models.BooleanField(
        default=False,
        help_text="Ajoute le recaptcha de Google pour empêcher les robots de s'inscrire.",
    )
    recaptcha_private = models.CharField(
        max_length=40, blank=True, help_text="Clé utilisée entre le serveur et google."
    )
    recaptcha_public = models.CharField(
        max_length=40,
        blank=True,
        help_text="Clé utilisée entre le client et le serveur.",
    )
    send_email_confirmation = models.BooleanField(
        default=False, help_text="Envoie un email de confirmation d'inscription."
    )
    beta_test = models.BooleanField(
        default=True,
        help_text="Permet d'afficher des messages qui préviennent les visiteurs que le site en version de test.",
    )
    rgpd = models.BooleanField(
        default=True,
        help_text="Permet d'afficher des messages en rapport au RGPD.",
    )

    def __str__(self):
        return self.site.name


class Place(models.Model):
    name = models.CharField(max_length=100)
    array = models.IntegerField()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        schedules = Schedule.objects.all()
        for s in schedules:
            a = Appointment(id="%s-%s" % (self.id, s.id), place=self, schedule=s)
            a.save()


class Schedule(models.Model):
    datetime = models.DateTimeField()

    class Meta:
        ordering = ["datetime"]

    def __str__(self):
        return self.datetime.isoformat()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        places = Place.objects.all()
        for p in places:
            a = Appointment(id="%s-%s" % (p.id, self.id), place=p, schedule=self)
            a.save()


class School(models.Model):
    SCHOOLS_CHOICE = (
        ("COS", "Collège de secteur"),
        ("COB", "Collège de bassin"),
        ("LYC", "Lycée"),
        ("LPR", "Lycée Professionnel"),
        ("OTH", "Autres étcblissements"),
    )
    name = models.CharField(max_length=400, verbose_name="Nom", unique=True)
    type_school = models.CharField(
        max_length=3, verbose_name="Type de lycée", choices=SCHOOLS_CHOICE
    )


class Student(models.Model):
    lastname = models.CharField(max_length=100, verbose_name="Nom")
    firstname = models.CharField(max_length=100, verbose_name="Prénom")
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    email = models.EmailField(
        unique=True,
        error_messages={"unique": "Un visiteur avec cet email s'est déjà inscrit."},
    )
    people = models.IntegerField(default=1, verbose_name="Nombre de personne")

    def __str__(self):
        return "%s %s" % (self.firstname, self.lastname)


class Appointment(models.Model):
    id = models.CharField(primary_key=True, max_length=100)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    students = models.ManyToManyField(Student)

    def __str__(self):
        return "%s, %s" % (self.schedule, self.place)
