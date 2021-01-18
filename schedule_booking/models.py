from django.db import models
from django.contrib.sites.models import Site
from django.core.validators import MaxValueValidator, MinValueValidator


class Config(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE)
    school = models.BooleanField(
        default=True, help_text="Demande de l'établissement d'origine."
    )
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
    caution_level = models.PositiveIntegerField(
        default=80,
        help_text="Taux d'occupation à partir duquel le créneau passe en orange. Si 100, le niveau n'est pas utilisé.",
    )
    warning_level = models.PositiveIntegerField(
        default=90,
        help_text="Taux d'occupation à partir duquel le créneau passe en rouge. Si 100, le niveau n'est pas utilisé.",
    )
    forbidden_level = models.PositiveIntegerField(
        default=100,
        help_text="Taux d'occupation à partir duquel l'insciption n'est plus possible. Devrait être à 100.",
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
    name = models.CharField(max_length=100, help_text="Nom du lieu")
    gauge = models.IntegerField(help_text="Jauge maxi")
    order = models.IntegerField(
        help_text="Numéro pour ordonner l'affichage des lieux", default=0
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        schedules = Schedule.objects.all()
        for s in schedules:
            a = Appointment(id="%s-%s" % (self.id, s.id), place=self, schedule=s)
            a.save()


class Schedule(models.Model):
    datetime = models.DateTimeField(help_text="Date et heure du créneau")
    authorizeds = models.CharField(
        max_length=300,
        default="CS CB AU",
        help_text="Authorisation en fonction de l'école (groupes espacés de 2 lettres)",
    )

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


class Student(models.Model):
    SCHOOLS_CHOICE = [
        (
            "Collèges de secteur",
            (
                ("CS01", "Collège René Guy Cadou (Montoir-de-Bretagne)"),
                ("CS02", "Collège Le Sacré Coeur (Pornichet)"),
                ("CS03", "Collège René Char (Saint-Joachim)"),
                ("CS04", "Collège Albert Vinçon (Saint-Nazaire)"),
                ("CSO5", "Collège Anita Conti (Saint-Nazaire)"),
                ("CS06", "Collège Jean Moulin (Saint-Nazaire)"),
                ("CS07", "Collège Pierre Norange (Saint-Nazaire)"),
                ("CS08", "Collège Saint Louis (Saint-Nazaire)"),
                ("CS09", "Collège Sainte Thérèse (Saint-Nazaire)"),
                ("CS10", "Collège Julien Lambot (Trignac)"),
            ),
        ),
        (
            "Collèges de bassin",
            (
                ("CB01", "Collège Arthur Rimbaud (Donges)"),
                ("CB02", "Collège Du Pays Blanc (Guérande)"),
                ("CB03", "Collège Jacques Brel (Guérande)"),
                ("CB04", "Collège Saint Jean-Baptiste (Guérande)"),
                ("CB05", "Collège Jacques Prévert (Herbignac)"),
                ("CB06", "Collège Saint Joseph (Herbignac)"),
                ("CB07", "Collège Éric Tabarly (La Baule-Escoublac)"),
                ("CB08", "Collège Grand Air (La Baule-Escoublac)"),
                ("CB09", "Collège Jules Verne (Le Pouliguen)"),
                ("CB10", "Collège La Fontaine (Missillac)"),
                ("CB11", "Collège Louise Michel (Paimboeuf)"),
                ("CB12", "Collège Frida Kahlo (Pontchâteau)"),
                ("CB13", "Collège Quéral (Pontchâteau)"),
                ("CB14", "Collège Saint Martin (Pontchâteau)"),
                ("CB15", "Collège Jean Mounes (Pornic)"),
                ("CB16", "Collège Notre Dame De Recouvrance (Pornic)"),
                ("CB17", "Collège Jean Mounes (Pornic)"),
                ("CB18", "Collège Hélène et René Guy Cadou (Saint-Brévin-les-Pins)"),
                ("CB19", "Collège Saint Joseph (Saint-Brévin-les-Pins)"),
                ("CB20", "Collège Gabriel Deshayes (Saint-Gildas-des-Bois)"),
                ("CB21", "Collège Antoine de Saint-Exupéry (Savenay)"),
                ("CB22", "Collège Mona Ozouf (Savenay)"),
                ("CB23", "Collège Saint Joseph (Savenay)"),
            ),
        ),
        (
            "Autres",
            (
                ("CB24", "Autre collège"),
                ("AU02", "Lycée général ou technologique"),
                ("AU03", "Lycée professionel"),
                ("CB25", "Autre"),
            ),
        ),
    ]

    class Meta:
        ordering = ["email"]

    lastname = models.CharField(max_length=100, verbose_name="Nom")
    firstname = models.CharField(max_length=100, verbose_name="Prénom")
    school = models.CharField(
        max_length=4,
        choices=SCHOOLS_CHOICE,
        default="AU02",
        verbose_name="Etablissement d'origine",
    )
    email = models.EmailField(
        unique=True,
        error_messages={"unique": "Un visiteur avec cet email s'est déjà inscrit."},
    )
    people = models.IntegerField(default=1, verbose_name="Nombre de personne")

    def __str__(self):
        return "%s %s (%s)" % (self.firstname, self.lastname, self.email)


class Appointment(models.Model):
    id = models.CharField(primary_key=True, max_length=100)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    students = models.ManyToManyField(Student)

    def __str__(self):
        return "%s, %s" % (self.schedule, self.place)
