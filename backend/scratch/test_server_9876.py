
from fastapi import FastAPI
import uvicorn
import time

app = FastAPI()

@app.get("/test")
def test():
    return {"status": "ok", "time": time.time()}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9876)
