This setup show how to easily manage and deploy BCH infrastructure with with one simple command.

This will spin up a BCHN node, a fulcrum indexer and a seperate script to automate SSL certificate renewals.

this only requirement here is having your DNS nameserver set to cloudflare (other options are possible bul will require a bit more changes to the YAML file).

Currently only the credentials from your Nameserver need to be updated in the file and you are ready to go. 

Install docker

    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh

create folder

    mkdir BCHinfra && cd BCHinfra

paste bchs_with_fulcrum.yaml here

Edit for your credentials

then deploy the stack:

    docker compose up

tadaa!!!


you will still need to open ports of you want your setup te be available from outside

