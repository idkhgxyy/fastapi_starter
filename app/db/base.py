from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 声明式基类。
    所有的数据模型都将继承自这个类，用于将 Python 类映射到数据库表。
    """
    pass
