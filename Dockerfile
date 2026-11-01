FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8
LABEL org.opencontainers.image.version="1.2.0.1"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock /build/requirements.lock
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r /build/requirements.lock
COPY src/app/ /app/
RUN chmod -R a+rX /app
USER 10001:10001
CMD ["python", "-B", "/app/bot.py"]
