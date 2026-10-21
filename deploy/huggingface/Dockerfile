# NoteMind backend on a Hugging Face Docker Space (free CPU tier: 2 vCPU, 16 GB RAM).
# Runs the API and both background workers in one container, from the image CD publishes.
# Setup: docs/DEPLOY.md. The GHCR package must be public for the Space to pull it.
FROM ghcr.io/adityaxsahni/notemind-backend:latest

USER root
# Spaces run the container as uid 1000 (the image's "app" user) with a writable /data only
# when persistent storage is enabled; uploads otherwise live in /tmp until a restart.
RUN mkdir -p /tmp/uploads && chown app:app /tmp/uploads
COPY --chown=app:app start.sh /app/start.sh
RUN chmod +x /app/start.sh
USER app

ENV UPLOAD_DIR=/tmp/uploads WEB_CONCURRENCY=2 OMP_NUM_THREADS=2
EXPOSE 7860
CMD ["/app/start.sh"]
