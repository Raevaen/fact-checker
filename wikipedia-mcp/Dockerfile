FROM python:3.12-slim

RUN pip install --no-cache-dir wikipedia-mcp

# Run as non-root
RUN useradd --create-home mcp
USER mcp

EXPOSE 8080

ENTRYPOINT ["wikipedia-mcp"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8080", "--path", "/mcp", "--enable-cache"]
