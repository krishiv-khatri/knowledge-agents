from typing import Any, Dict
from sqlalchemy.orm import DeclarativeBase, relationship, declared_attr
from sqlalchemy.orm import mapped_column

class Base(DeclarativeBase):

    def as_dict(self) -> Dict[str, Any]:
        result = {}
        for c in self.__table__.columns:
            v = getattr(self, c.name)
            if (isinstance(v, Dict)):
                result[c.name] = v
            else:
                result[c.name] = str(v)
        return result
