FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y gcc libc-dev

COPY . /app

RUN gcc -shared -fPIC -o Engine.so Engine.c -O2
RUN pip install fastapi sqlalchemy httpx uvicorn pydantic

CMD ["uvicorn", "main_orchestrator:app", "--host", "0.0.0.0", "--port", "8000"]
