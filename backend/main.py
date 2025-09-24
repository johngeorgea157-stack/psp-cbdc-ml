from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "PSP + CBDC + AI/ML Project Skeleton Running 🚀"}