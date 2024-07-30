build:
	cd app && docker build -t komrogrs .

compose: build
	docker-compose up

stop:
	docker-compose down

update:
	/bin/bash copy2container.sh