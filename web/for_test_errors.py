@app.get("/test_404")
async def test_404():
    raise HTTPException(status_code=404, detail="Тестовая страница не найдена")


@app.get("/test_500")
async def test_500():
    result = 1 / 0
    return {"result": result}

class TestModel(BaseModel):
    name: str
    age: int

@app.post("/test_validation/")
async def test_validation(data: TestModel):
    return data