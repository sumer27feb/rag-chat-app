import sys
from loguru import logger
from pathlib import Path
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

# Create logs folder
Path("logs").mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# Loguru handlers
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{message}</cyan>",
    level="INFO",
)
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)

# ---------------- Sentry Integration ----------------
sentry_logging = LoggingIntegration(
    level=None,          # capture all logs
    event_level="ERROR"  # send ERROR+ logs to Sentry
)

sentry_sdk.init(
    dsn="https://d35e7f827a780945aed96d1420b8e9e5@o4509181138829312.ingest.us.sentry.io/4510154975805440",        # <— replace with your Sentry DSN
    integrations=[sentry_logging],
    traces_sample_rate=1.0,       # capture performance traces
    environment="development",    # or "production"
)

__all__ = ["logger", "sentry_sdk", "SentryAsgiMiddleware"]
