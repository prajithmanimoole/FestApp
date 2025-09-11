from event_app.app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Get port from environment variable or use 8080 as default
    try:
        port_value = os.environ.get("PORT", "8080")
        # Handle the literal string '$PORT' that might be passed by Railway
        if port_value == '$PORT':
            print("Warning: Received literal '$PORT' string. Using default port 8080.")
            port = 8080
        else:
            port = int(port_value)
    except ValueError:
        # If PORT is not a valid integer, use default port
        print(f"Warning: PORT environment variable '{port_value}' is not a valid integer. Using default port 8080.")
        port = 8080
    app.run(host="0.0.0.0", port=port)