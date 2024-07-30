Eine kleine Einführung: https://www.dev-insider.de/was-ist-docker-a-733683/

Schaue dir nun das Dockerfile in einem Texteditor an.


Baue ein Docker Image indem du dich in der Shell im Hauptverzeichnis deines Projektes befindest
und den Befehl "docker build -t azubi-docker ." ausführst. 


Der Zusatz "-t" ist die Kurzform von "--tag" und wird für die Namensgebung, in dem Fall "azubi-docker" benötigt.


Anschließend kannst du mit dem Befehl "docker image ls" dein neu erstelltes Image und weitere Informationen,
unter anderem die Image ID sehen.


Mit dem Befehl "docker run -t -i image_id" kannst du den Container starten.
Zunächst wird das Betriebssystem Linux Alpine in dem Container installiert und anschließend erscheint die Alpine shell in deiner Kommandozeile.
Hierfür sind die Befehle "-t" (im Kontext mit run anders als bei build) und "-i" verantwortlich.
Dies führt dazu, dass die Alpine shell in der Windows shell angezeigt wird (-t), und die Befehle weitergeleitet(-i) werden.


Nun kannst du ein neues shell Fenster öffnen und mit dem Befehl "docker ps" die laufenden Container überwachen.


Die shell kann mit exit verlassen werden, der Container stoppt nun automatisch und kann neu gestartet werden.


Images werden mit dem Befehl "docker rmi -f image_name:latest" wieder gelöscht um Speicherplatz freizugeben.
"rmi" steht hier für remove image und "-f" für force.
Falls du den Namen des Image nicht mehr weißt, kannst du wie oben beschrieben mit docker image ls deine Images anzeigen.
