# Opakované ověření uložených diffů: obraz úlohy + unzip (test validateDocx v spec-pipeline
# ho volá; v obrazu agenta chyběl, sada úlohy 02 proto padala nezávisle na řešení).
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends unzip && rm -rf /var/lib/apt/lists/*
USER node
