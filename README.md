# Running the Inference App

## 🛠️ Setup Instructions

1. Create a virtual environment

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

2. Set up the required environment variables in the [configuration file](./config.py) or by using a `.env` file.

3. Start the MCP client

   ```bash
   uvicorn client_api:app --reload
   ```

4. Start the ClusterIQ API.
5. You can use [FastAPI UI](http://127.0.0.1:8000/docs) to interact with the API or using any available tool like `curl`

Example requests:

```text
Give me an overview of the current inventory
```

```bash
curl --location --request POST 'http://127.0.0.1:8000/chat' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "Give me an overview of the current inventory"
}'
```

```text
Which cluster has the highest number of instances?
```

```bash
curl --location --request POST 'http://127.0.0.1:8000/chat' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "Which cluster has the highest number of instances?"
}'
```

```text
How many GCP accounts are in the current inventory?
```

```bash
curl --location --request POST 'http://127.0.0.1:8000/chat' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "How many GCP accounts are in the current inventory?"
}'
```

```text
Which account has the most clusters?
```

```bash
curl --location --request POST 'http://127.0.0.1:8000/chat' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "Which account has the most clusters?"
}'
```

```text
Which cluster has been running the longest?
```

```bash
curl --location --request POST 'http://127.0.0.1:8000/chat' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "Which cluster has been running the longest?"
}'
```

```text
List the top 5 oldest clusters by creation date.
```

```bash
curl --location --request POST 'http://127.0.0.1:8000/chat' \
--header 'Content-Type: application/json' \
--data-raw '{
    "query": "List the top 5 oldest clusters by creation date."
}'
```
