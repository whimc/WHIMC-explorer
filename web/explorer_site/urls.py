from django.urls import path
from portal import views
from portal import comparison
from portal import export_queue

urlpatterns = [
    path('request-exports/', export_queue.page, name='request-exports'),
    path('api/worker/poll/', export_queue.poll, name='worker-poll'),
    path('api/worker/result/', export_queue.result, name='worker-result'),
    path("", views.index, name="index"),
    path("compare/", comparison.page, name="compare"),
    path("api/comparison/options/", comparison.options, name="comparison-options"),
    path("api/comparison/paths/", comparison.paths, name="comparison-paths"),
    path("import/", views.import_bundle, name="import"),
    path('sessions/<uuid:bundle_id>/labels/', views.study_labels, name='study-labels'),
    path("api/sessions/", views.sessions, name="sessions"),
    path("api/sessions/<uuid:bundle_id>/", views.detail, name="detail"),
    path("exports/<uuid:bundle_id>/", views.download, name="download"),
]
