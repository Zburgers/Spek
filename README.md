Spek

Multimodal AI platform with Text, Live Voice, Documents and Mobile Automation.

We appretiate open source contributions.

Run with:

- Start docker service:

sudo systemctl start docker

docker compose up -d --build
- This builds and runs the server in the background

or simply:

docker compose up --build

To terminate sever:

docker compose down

To start a static server and view the frontend you can host a http server listening on a specific port:

python3 -m http.server [PORT]

Example:
python3 -m http.server 8081 
[PORT] = 8081