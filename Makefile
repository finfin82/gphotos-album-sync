# gphotos-album-sync

.PHONY: up down logs config test build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

config:
	docker compose config

build:
	docker compose build

test:
	python3 -m pytest -q
