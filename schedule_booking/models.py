from django.db import models
from django.contrib.sites.models import Site


class Config(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE)
    group = models.BooleanField(default=True)
    caution_level = models.FloatField(default=8)
    warning_level = models.FloatField(default=4)
    forbidden_level = models.FloatField(default=3)

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


class Student(models.Model):
    lastname = models.CharField(max_length=100)
    firstname = models.CharField(max_length=100)
    email = models.EmailField(
        unique=True,
        error_messages={"unique": "Un visiteur avec cet email s'est déjà inscrit."},
    )
    people = models.IntegerField(default=1)

    def __str__(self):
        return "%s %s" % (self.firstname, self.lastname)


class Appointment(models.Model):
    id = models.CharField(primary_key=True, max_length=100)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    students = models.ManyToManyField(Student)

    def __str__(self):
        return "%s, %s" % (self.schedule, self.place)
