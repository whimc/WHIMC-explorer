from django.conf import settings
from django.db import OperationalError, IntegrityError
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from .models import SessionBundle
from .storage import store_bundle
import json
from django.utils import timezone
from .forms import StudyLabelsForm


@require_http_methods(['GET', 'POST'])
def study_labels(request, bundle_id):
    if not request.can_import:
        return HttpResponseForbidden('Only authorized importers can edit study labels.')
    record = get_object_or_404(SessionBundle, pk=bundle_id)
    form = StudyLabelsForm(request.POST if request.method == 'POST' else None,
                          initial={key: getattr(record, key) for key in ('study', 'location', 'session_name')})
    if request.method == 'POST' and form.is_valid():
        SessionBundle.objects.filter(pk=record.pk).update(**form.cleaned_data, labels_updated_by=request.evaluator, labels_updated_at=timezone.now())
        return redirect(reverse('index') + '?session=' + str(record.id))
    return render(request, 'portal/study_labels.html', {'form': form, 'record': record}, status=400 if form.is_bound and not form.is_valid() else 200)


@require_GET
def index(request):
    return render(request, "portal/index.html", {"demo": settings.DEMO})


@require_http_methods(["GET", "POST"])
def import_bundle(request):
    if not request.can_import:
        return HttpResponseForbidden("This NetID does not have import permission.")
    error = None
    if request.method == "POST":
        upload = request.FILES.get("bundle")
        try:
            if upload is None or upload.size > settings.MAX_BUNDLE_BYTES:
                raise ValueError("Choose one Explorer JSON bundle, up to 8 MB")
            record, created = store_bundle(upload.read(settings.MAX_BUNDLE_BYTES + 1), request.evaluator)
            return redirect(reverse("index") + "?session=" + str(record.id))
        except (ValueError, TypeError, RecursionError):
            error = "This bundle is invalid or exceeds the import limits. Validate it with the Windows exporter."
        except (OperationalError, IntegrityError):
            error = "The database is busy. Please retry the import; repeated bundles are safe."
    return render(request, "portal/import.html", {"error": error}, status=400 if error else 200)


@require_GET
def sessions(request):
    try:
        page = int(request.GET.get("page", "1"))
        if not 1 <= page <= 100:
            raise ValueError()
    except ValueError:
        return JsonResponse({"error": "Invalid page"}, status=400)
    query = SessionBundle.objects.order_by("-start", "id")
    total = query.count()
    records = query[(page - 1) * 50:page * 50]
    return JsonResponse({"page": page, "has_more": page * 50 < total, "total": total, "sessions": [
        {"id": str(r.id), "label": r.player_label, "server": r.server_id, "start": r.start, "end": r.end,
         "study": r.study, "location": r.location, "session_name": r.session_name,
         "labels_url": reverse('study-labels', args=[r.id]) if request.can_import else None,
         "catalog": r.catalog_version, "url": reverse("detail", args=[r.id]), "download": reverse("download", args=[r.id])}
        for r in records.defer("payload", "metrics")
    ]})


@require_GET
def detail(request, bundle_id):
    record = get_object_or_404(SessionBundle, pk=bundle_id)
    return JsonResponse({"bundle": record.payload, "metrics": record.metrics, "digest": record.digest,
                         "labels": {key: getattr(record, key) for key in ('study', 'location', 'session_name', 'labels_updated_by', 'labels_updated_at')}})


@require_GET
def download(request, bundle_id):
    record = get_object_or_404(SessionBundle, pk=bundle_id)
    response = HttpResponse(json.dumps(record.payload, allow_nan=False), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="explorer-{record.id}.json"'
    return response
