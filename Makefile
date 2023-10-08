#!/usr/bin/env make

build:
	docker build -t bancho-service:latest .

run:
	docker run -p ${APP_PORT}:${APP_PORT} -it bancho-service:latest

run-bg:
	docker run -p ${APP_PORT}:${APP_PORT} -d bancho-service:latest
