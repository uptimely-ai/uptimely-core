FROM python:3.13-slim

ENV POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

COPY install-python.sh /tmp/install-python.sh
RUN bash /tmp/install-python.sh && rm /tmp/install-python.sh

# Set workdir
WORKDIR /workspace
