from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.modules.users import models as user_models  # noqa: E402,F401
from app.modules.vehicles import models as vehicle_models  # noqa: E402,F401
from app.modules.workshops import models as workshop_models  # noqa: E402,F401
