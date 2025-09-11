from event_app.app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Get port from environment variable or use 8080 as default
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)