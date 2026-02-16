from django.urls import path
from . import views

app_name = "support"

urlpatterns = [
    path("help-center/", views.help_center, name="help_center"),
    path("help-center/<slug:slug>/", views.article_detail, name="article_detail"),

    path("training-guides/", views.training_guides, name="training_guides"),
    path("training-guides/<slug:slug>/", views.guide_detail, name="guide_detail"),

    path("contact-support/", views.contact_support, name="contact_support"),
    path("ticket/<uuid:ticket_id>/", views.ticket_detail, name="ticket_detail"),

    # Guided tours (onboarding)
    path("guided-tours/", views.guided_tours, name="guided_tours"),
    path("guided-tours/toggle/<int:item_id>/", views.toggle_onboarding_item, name="toggle_onboarding_item"),
]
