FROM python:3.14-slim
WORKDIR /app

COPY app.py requirements.txt .


RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["python", "app.py"]