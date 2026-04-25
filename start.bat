@echo off
echo ========================================
echo    🤖 LicitaBot - Iniciando Servidor
echo ========================================
echo.

echo ✅ Verificando dependências...
pip install -r requirements.txt

echo.
echo ✅ Iniciando servidor FastAPI...
echo 📍 Acesse: http://localhost:8000/docs
echo.

python -m uvicorn main:app --reload --port 8000

start "" http://127.0.0.1:8080/index.html

pause