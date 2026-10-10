from django.db import migrations, models


def index_worlds(apps, schema_editor):
    Bundle = apps.get_model('portal', 'SessionBundle')
    for row in Bundle.objects.using(schema_editor.connection.alias).only('id', 'payload').iterator(chunk_size=1):
        Bundle.objects.using(schema_editor.connection.alias).filter(pk=row.pk).update(world_names=sorted(row.payload['worlds']))


class Migration(migrations.Migration):
    dependencies = [('portal', '0001_initial')]
    operations = [
        migrations.AddField(model_name='sessionbundle', name='world_names', field=models.JSONField(default=list)),
        migrations.RunPython(index_worlds, migrations.RunPython.noop),
    ]
