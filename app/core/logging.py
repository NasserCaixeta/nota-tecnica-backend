import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # HTTP clients otherwise log full URLs, including storage signatures.
    for name in ("httpx", "httpcore", "botocore", "boto3", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
