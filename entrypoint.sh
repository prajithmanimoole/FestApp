#!/bin/bash
set -e

# Print environment variables for debugging
echo "Environment variables:"
printenv

# Explicitly set the port to use
if [ -n "$PORT" ]; then
  echo "Using provided PORT: $PORT"
  export GUNICORN_PORT="$PORT"
else
  echo "PORT not set, using default 8080"
  export GUNICORN_PORT="8080"
fi

# Start gunicorn with the explicit port value
echo "Starting gunicorn on port $GUNICORN_PORT"
exec gunicorn --bind "0.0.0.0:$GUNICORN_PORT" wsgi:app
