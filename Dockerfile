FROM python:3.9

COPY requirements.txt .
RUN pip install -r requirements.txt

# COPY scripts /scripts
# RUN chmod u+x /scripts/*
# RUN ln -s /scripts/wait-for-it.sh /usr/local/bin/wait-for-it

COPY . /srv/root

EXPOSE 80

WORKDIR /srv/root

CMD ["./main.py"]
