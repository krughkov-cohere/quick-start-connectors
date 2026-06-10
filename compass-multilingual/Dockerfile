FROM python:3.11-slim
WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-interaction
COPY . .
EXPOSE 5000
CMD ["poetry", "run", "flask", "--app", "provider", "run", "--host", "0.0.0.0", "--port", "5000"]
