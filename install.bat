@echo off
echo ========================================
echo    🤖 LicitaBot - Instalação Inicial
echo ========================================
echo.

echo ✅ Verificando Python...
python --version
if %errorlevel% neq 0 (
    echo ❌ Python não encontrado! Instale Python 3.8+ primeiro.
    echo 📥 Download: https://python.org/downloads
    pause
    exit /b 1
)

echo.
echo ✅ Instalando dependências...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ✅ Testando instalação...
python -c "import fastapi, uvicorn; print('✅ Instalação concluída com sucesso!')"

echo.
echo 🚀 Para iniciar o servidor, execute: start.bat
echo 📖 Leia o README.md para mais informações
echo.

pause