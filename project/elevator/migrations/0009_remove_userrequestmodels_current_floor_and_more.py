# Generated by Django 4.2.1 on 2023-06-01 15:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elevator', '0008_elevatorsmodel_first_floor_elevatorsmodel_last_floor'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userrequestmodels',
            name='current_floor',
        ),
        migrations.AddField(
            model_name='userrequestmodels',
            name='destination_floor',
            field=models.IntegerField(default=0),
        ),
    ]
