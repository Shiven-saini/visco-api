import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8086,
        reload=True  # Set to False in production : Shiven Saini
    )
