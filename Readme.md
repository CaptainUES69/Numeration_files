Для запуска через докер:
    docker run -v ${PWD}/output:/app/operators "Имя образа" - Powershell
    docker run -v %cd%/output:/app/operators "Имя образа" - CMD
    docker run -v $(pwd)/output:/app/operators "Имя образа" - Linux