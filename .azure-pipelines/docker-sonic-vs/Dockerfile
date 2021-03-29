FROM docker-sonic-vs

ARG docker_container_name

ADD ["wheels", "/wheels"]

RUN pip3 install --no-deps --force-reinstall /wheels/sonic_utilities-1.2-py3-none-any.whl
