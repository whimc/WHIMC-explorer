"""Manage imported sessions and explicitly saved camp/team collections."""
import json
import tempfile
import zipfile
from django import forms
from django.db import transaction
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods
from .models import Collection, SessionBundle


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name', 'sessions']
        widgets = {'sessions': forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sessions'].queryset = SessionBundle.objects.defer('payload', 'metrics').order_by('-start')
        self.fields['sessions'].label_from_instance = lambda s: f'{s.player_label} · {s.study} · {s.session_name} · {s.server_id} · {s.id}'


@require_GET
def page(request):
    return render(request, 'portal/library.html', {
        'collections': Collection.objects.order_by('name'),
        'sessions': SessionBundle.objects.defer('payload', 'metrics').order_by('-start'),
    })


@require_http_methods(['GET', 'POST'])
def edit(request, collection_id=None):
    if not request.can_import:
        return HttpResponseForbidden('Import permission required.')
    instance = get_object_or_404(Collection, pk=collection_id) if collection_id else None
    form = CollectionForm(request.POST if request.method == 'POST' else None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            if instance is None:
                item.created_by = request.evaluator
            item.save()
            form.save_m2m()
        return redirect('library')
    return render(request, 'portal/collection_edit.html', {'form': form}, status=400 if form.errors else 200)


@require_http_methods(['GET', 'POST'])
def remove(request, bundle_id):
    if not request.can_import:
        return HttpResponseForbidden('Import permission required.')
    record = get_object_or_404(SessionBundle, pk=bundle_id)
    if request.method == 'POST' and request.POST.get('confirm') == str(record.id):
        record.delete()
        return redirect('library')
    return render(request, 'portal/session_remove.html', {'record': record})


@require_GET
def download(request, collection_id):
    item = get_object_or_404(Collection, pk=collection_id)
    output = tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024)
    try:
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            manifest = {'format': 'whimc-explorer.collection.v1', 'name': item.name, 'sessions': []}
            for record in item.sessions.all().iterator(chunk_size=1):
                name = f'explorer-{record.id}.json'
                archive.writestr(name, json.dumps(record.payload, allow_nan=False))
                manifest['sessions'].append({'file': name, 'study': record.study,
                    'location': record.location, 'session_name': record.session_name})
            archive.writestr('collection-manifest.json', json.dumps(manifest))
        output.seek(0)
        return FileResponse(output, as_attachment=True, filename=f'camp-{item.id}.zip')
    except Exception:
        output.close()
        raise
