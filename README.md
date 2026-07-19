# FastAPI-Project
My first try into exploring FastAPI framework

Client: Gets PC metrics and sends it to the server  
Server: FastAPI server is recieving metrics from a client and sends it to Redis and RabbitMQ.  
Redis: Most recent data can be accessed with FastAPI Redis get request.  
Broker: RabbitMQ sends messages queues to DB and Alert workers.  
Alert Worker: Gets data from queue, checks thresholds and sends alerts.  
DB Worker: Gets data from queue and puts it in PostgreSQL table.  
TG Bot: Sends alerts and reqests data through FastAPI server.

#TODO LIST:  
#TODO RabbitMQ -> DB for longterm storage | DONE!  
#TODO TG bot or similar to recieve alerts or request current/all-time metrics data. | DONE!  
#TODO Wrap everything into docker containers | DONE!  
    monitoring_client_send.py supposed to be ran as a service on a local machine, everything other than that runs on a server as a docker container.