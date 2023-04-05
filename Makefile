#!/usr/bin/make

build:
	docker build -t bancho-service:latest -t registry.digitalocean.com/akatsuki/bancho-service:latest .

push:
	docker push registry.digitalocean.com/akatsuki/bancho-service:latest

install:
	helm install --values chart/values.yaml bancho-service-staging ../akatsuki/common-helm-charts/microservice-base/

uninstall:
	helm uninstall bancho-service-staging

diff-upgrade:
	helm diff upgrade --allow-unreleased --values chart/values.yaml bancho-service-staging ../akatsuki/common-helm-charts/microservice-base/

upgrade:
	helm upgrade --atomic --values chart/values.yaml bancho-service-staging ../akatsuki/common-helm-charts/microservice-base/
