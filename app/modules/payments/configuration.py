from app.core.config import Settings


def webhook_configuration_ready(settings: Settings) -> bool:
    secret = settings.asaas_webhook_token.get_secret_value()
    return (
        settings.payments_enabled
        and len(secret) >= 32
        and secret != settings.asaas_api_key.get_secret_value()
    )
