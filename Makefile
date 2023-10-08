#!/usr/bin/env make

build:
	docker build -t bancho-service:latest .

run:
	docker run --network=host -it bancho-service:latest

run-bg:
	docker run --network=host -d bancho-service:latest
