FROM docker-sonic-vs

ARG docker_container_name

ADD ["wheels", "/wheels"]

# Uninstalls only sonic-utilities and does not impact its dependencies
RUN pip3 uninstall -y sonic-utilities

# Installs sonic-utilities, adds missing dependencies, upgrades out-dated depndencies
RUN pip3 install /wheels/sonic_utilities-1.2-py3-none-any.whl
