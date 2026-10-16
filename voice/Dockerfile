FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
RUN pip install .
ENV PORT=8080
# No access log (app/main.py also redacts media-stream URLs, whose query is a bearer token).
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-access-log
