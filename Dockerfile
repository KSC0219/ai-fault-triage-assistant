FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000 8501
# API by default; for the UI run: docker run -p 8501:8501 <image> streamlit run ui/streamlit_app.py --server.address 0.0.0.0
CMD ["uvicorn", "triage.api:app", "--host", "0.0.0.0", "--port", "8000"]
