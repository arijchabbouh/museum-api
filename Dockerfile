FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt . 
RUN python -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim 
ENV PATH="/venv/bin:$PATH" PYTHONUNBUFFEERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --uid 10001 appuser
WORKDIR /srv
COPY --from=build /venv /venv
COPY app/ ./app
USER 10001
EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0:8080", "-w", "1", "--threads", "4", "app.main:app"]