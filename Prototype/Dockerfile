FROM python:3.14-slim

RUN pip install --no-cache-dir streamlit python-dotenv otari

WORKDIR /app
COPY main.py mainfunctions.py ./

# Run as non-root
RUN useradd --create-home app
USER app

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "main.py"]
CMD ["--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
