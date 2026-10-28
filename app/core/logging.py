import logging


class ExceptionPrivacyFilter(logging.Filter):
    def filter(self, record):
        if record.exc_info:
            error_type = record.exc_info[0].__name__
            # Server/task loggers may render both exception values in args and
            # SQL-bound parameters in the traceback. Keep classification only.
            record.msg = "Unhandled failure (%s)"
            record.args = (error_type,)
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


_exception_privacy_filter = ExceptionPrivacyFilter()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # HTTP clients otherwise log full URLs, including storage signatures.
    for name in ("httpx", "httpcore", "botocore", "boto3", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)

    for name in ("uvicorn.error", "celery.app.trace", "celery.worker.request"):
        logging.getLogger(name).addFilter(_exception_privacy_filter)
