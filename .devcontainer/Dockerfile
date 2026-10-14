FROM python:3.13-slim

ENV POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

COPY scripts/install-python-tooling.sh /tmp/install-python-tooling.sh
RUN bash /tmp/install-python-tooling.sh && rm /tmp/install-python-tooling.sh

# Set workdir
WORKDIR /workspace
