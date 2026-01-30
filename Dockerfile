# Use an official Python runtime with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set the working directory to /app
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy the project files
COPY . .

# Install dependencies
RUN uv sync

# Expose port 8000
EXPOSE 8000

# Run the application with proxy headers enabled (for proper URL generation behind Nginx/Traefik)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
