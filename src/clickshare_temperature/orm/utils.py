from __future__ import annotations


from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import SelectBase
from sqlalchemy import func, select



def get_count_for_select(select_stmt: SelectBase, session: Session) -> int:
    """Get the count of rows for a given select statement

    Arguments:
        select_stmt: The select statement to count rows for
        session: The SQLAlchemy session to use for database operations

    Returns:
        The number of rows for the given select statement
    """
    count_stmt = select(func.count()).select_from(select_stmt.subquery())
    result = session.execute(count_stmt).scalar_one()
    return result
