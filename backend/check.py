import traceback
import sys

try:
    from app.core.config import settings
    print("CONFIG OK")
    print("APP_ENV:", settings.APP_ENV)
except Exception:
    print("CONFIG FAILED")
    traceback.print_exc()
    sys.exit(1)

try:
    from app.core.database import Base
    print("DATABASE IMPORT OK")
except Exception:
    print("DATABASE IMPORT FAILED")
    traceback.print_exc()
    sys.exit(1)

try:
    from app.models import *
    print("MODELS OK")
except Exception:
    print("MODELS IMPORT FAILED")
    traceback.print_exc()
    sys.exit(1)

print("ALL CHECKS PASSED")