from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings


def main():
    url = str(settings.DATABASE_URL).replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()


if __name__ == "__main__":
    main()
