import json

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 建议替换为您的实际数据库配置
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:123456@localhost/sleep_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_sleep_record_model_columns():
    inspector = inspect(engine)
    if "sleep_records" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("sleep_records")}
    alter_statements = []

    if "model_family" not in existing_columns:
        alter_statements.append(
            "ALTER TABLE sleep_records ADD COLUMN model_family VARCHAR(100) NULL"
        )
    if "model_name" not in existing_columns:
        alter_statements.append(
            "ALTER TABLE sleep_records ADD COLUMN model_name VARCHAR(255) NULL"
        )

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))

    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                "SELECT id, result_json, model_family, model_name "
                "FROM sleep_records "
                "WHERE model_family IS NULL OR model_name IS NULL"
            )
        ).mappings().all()

        for row in rows:
            result_json = row["result_json"]
            if isinstance(result_json, str):
                try:
                    result_json = json.loads(result_json)
                except json.JSONDecodeError:
                    result_json = {}
            elif result_json is None:
                result_json = {}

            model_family = result_json.get("model_family") or row["model_family"] or "sleep_stage_v8"
            model_name = row["model_name"] or result_json.get("model_name")

            session.execute(
                text(
                    "UPDATE sleep_records "
                    "SET model_family = :model_family, model_name = :model_name "
                    "WHERE id = :record_id"
                ),
                {
                    "record_id": row["id"],
                    "model_family": model_family,
                    "model_name": model_name,
                },
            )

        session.commit()
    finally:
        session.close()


def ensure_database_schema():
    ensure_sleep_record_model_columns()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()