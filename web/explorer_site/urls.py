from django.urls import path
from portal import views
from portal import comparison

urlpatterns = [
    path("", views.index, name="index"),
    path("compare/", comparison.page, name="compare"),
    path("api/comparison/options/", comparison.options, name="comparison-options"),
    path("api/comparison/paths/", comparison.paths, name="comparison-paths"),
    path("import/", views.import_bundle, name="import"),
    path("api/sessions/", views.sessions, name="sessions"),
    path("api/sessions/<uuid:bundle_id>/", views.detail, name="detail"),
    path("exports/<uuid:bundle_id>/", views.download, name="download"),
]
