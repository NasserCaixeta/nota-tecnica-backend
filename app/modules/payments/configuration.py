from app.core.config import Settings
from app.integrations.payments.stripe import test_secret


def webhook_configuration_ready(settings: Settings) -> bool:
    secret = settings.stripe_webhook_secret.get_secret_value()
    key = settings.stripe_secret_key.get_secret_value()
    return (
        settings.payments_enabled
        and test_secret(key)
        and len(secret) >= 32
        and secret.startswith("whsec_")
        and secret != key
    )
