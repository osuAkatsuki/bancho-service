FROM python:3.9

COPY . /srv/root

WORKDIR /srv/root

RUN pip install -r requirements.txt
RUN pip install --upgrade pip

EXPOSE 80

CMD ["./scripts/start.sh"]
