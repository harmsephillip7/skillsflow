from django.db import migrations


def seed_providers(apps, schema_editor):
    IntegrationProvider = apps.get_model("integrations", "IntegrationProvider")

    # Only create if missing
    IntegrationProvider.objects.get_or_create(
        slug="whatsapp",
        defaults={
            "name": "WhatsApp Business (Cloud API)",
            "description": "Meta WhatsApp Cloud API integration for messaging and webhooks.",
            "category": "MESSAGING",
            "auth_type": "API_KEY",
            "supports_sync": False,
            "supports_webhooks": True,
            "supports_realtime": True,
            "is_active": True,
            "is_beta": True,
            # IMPORTANT: this must point at the connector class we use below
            "connector_class": "integrations.connectors.whatsapp.WhatsAppConnector",
        },
    )


def unseed_providers(apps, schema_editor):
    IntegrationProvider = apps.get_model("integrations", "IntegrationProvider")
    IntegrationProvider.objects.filter(slug="whatsapp").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0021_alter_integrationconnection_api_key_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_providers, reverse_code=unseed_providers),
    ]