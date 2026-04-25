# 💾 Guia de Backup e Versionamento - LicitaBot

## 🎯 Como Salvar Seu Projeto

### Opção 1: Backup Local (Recomendado para Iniciantes)

1. **Copie a pasta completa**
   ```
   Copie toda a pasta: c:\curso-html-sites\aula-html-1\licita-bot\
   Para: C:\Backups\LicitaBot-[DATA]\
   ```

2. **Compacte em ZIP**
   - Clique direito na pasta → "Enviar para" → "Pasta compactada"
   - Nome sugerido: `LicitaBot-v1.0-[DATA].zip`

### Opção 2: Google Drive / OneDrive

1. **Suba a pasta para nuvem**
   - Arraste a pasta `licita-bot` para seu Google Drive
   - Ou sincronize com OneDrive

2. **Compartilhe com sua equipe**
   - Clique direito → Compartilhar
   - Defina permissões (visualizar/editar)

### Opção 3: GitHub (Profissional)

1. **Crie repositório no GitHub**
   ```bash
   # No terminal, dentro da pasta licita-bot:
   git init
   git add .
   git commit -m "Versão inicial LicitaBot v1.0"
   git remote add origin https://github.com/SEU-USUARIO/licita-bot.git
   git push -u origin main
   ```

## 📋 Checklist de Backup

- [ ] Código fonte (`main.py`)
- [ ] Dependências (`requirements.txt`)
- [ ] Documentação (`README.md`)
- [ ] Scripts de instalação (`install.bat`, `start.bat`)
- [ ] Este guia (`BACKUP-GUIDE.md`)

## 🔄 Versionamento Sugerido

### v1.0 - MVP Atual
- ✅ API básica com FastAPI
- ✅ Simulação de lances
- ✅ Estratégias simples

### v1.1 - Próxima Versão
- [ ] Banco de dados SQLite
- [ ] Autenticação básica
- [ ] Interface web simples

### v2.0 - Versão Comercial
- [ ] Integração real com portais
- [ ] Dashboard completo
- [ ] Sistema de pagamento

## 🚨 Importante

1. **Faça backup ANTES de grandes mudanças**
2. **Teste sempre em cópia antes de alterar o original**
3. **Mantenha pelo menos 3 versões salvas**
4. **Documente todas as alterações importantes**

## 📞 Recuperação de Emergência

Se algo der errado:
1. Pare o servidor (Ctrl+C no terminal)
2. Restaure o backup mais recente
3. Execute `install.bat` novamente
4. Teste com `start.bat`

---
**💡 Dica:** Sempre que adicionar nova funcionalidade, crie um novo backup!