from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/support_simulator"

    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    UPLOAD_DIR: str = "uploads/documents"
    MAX_UPLOAD_MB: int = 20

    FIRST_ADMIN_EMAIL: str = "admin@example.com"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"
    FIRST_ADMIN_NAME: str = "Super Admin"

    class Config:
        env_file = ".env"


settings = Settings()
