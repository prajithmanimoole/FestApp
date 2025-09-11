from event_app.app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Get port from environment variable with robust error handling
    port_value = os.environ.get("PORT", "8080")
    
    # Handle various edge cases for PORT environment variable
    if port_value in ['$PORT', '', None]:
        print(f"Warning: Invalid PORT value '{port_value}'. Using default port 8080.")
        port = 8080
    else:
        try:
            port = int(port_value)
            # Validate port range
            if port < 1 or port > 65535:
                print(f"Warning: PORT {port} is out of valid range. Using default port 8080.")
                port = 8080
        except (ValueError, TypeError):
            print(f"Warning: PORT environment variable '{port_value}' is not a valid integer. Using default port 8080.")
            port = 8080
    
    print(f"Starting Flask app on host 0.0.0.0 and port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)