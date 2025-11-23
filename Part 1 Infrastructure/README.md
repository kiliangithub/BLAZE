Install docker

    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh

create folder

    mkdir BCHinfra && cd BCHinfra

paste bchs_with_fulcrum.yaml here

Eddit for your credentials

then deploy the stack:

    docker compose up

tadaa!!!

you will still need to open ports of you want your setup te be available from outside

