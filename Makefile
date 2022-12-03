build:
	docker build -t bancho-service:latest .

run:
	docker run --network=host --env-file=.env bancho-service:latest

create-venv:
	python3.9 -m virtualenv venv && source venv/bin/activate && pip install -r requirements.txt

update-venv:
	source venv/bin/activate && pip install -Ur requirements.txt
