# FastAPI-Project
My first try into exploring FastAPI framework

FastAPI local server with RabbitMQ and Redis recieving monitoring metrics data from a client.  
Most recent data can be accessed with FastAPI Redis request.  
Messages queue can be accessed by RabbitMQ request.  
#TODO RabbitMQ -> DB for longterm storage  
#TODO TG bot or similar to recieve alerts or request current/all-time metrics data.  
#TODO Wrap everything into docker containers | DONE!  
    monitoring_client_send.py supposed to be ran as a service on a local machine, everything other than that runs on a server as a docker container