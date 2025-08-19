from setuptools import setup, find_packages

setup(
    name="zivohealth",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "alembic",
        "psycopg2-binary",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "python-multipart",
        "redis",
        "openai",
        "python-dotenv",
        "pydantic",
        "pydantic-settings",
        "websockets",
        "pytest",
        "httpx",
    ],
) 