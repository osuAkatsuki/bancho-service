FROM python:3.9

COPY . /app

WORKDIR /app

RUN pip install -r requirements.txt
RUN pip install --upgrade pip

EXPOSE 80

CMD ["python", "main.py"]
