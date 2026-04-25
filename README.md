# 🤖 LicitaBot - Sistema de Automação para Licitações

Sistema completo para automação de lances em portais de licitação eletrônica como Comprasnet e Licitações-e.

## 📋 Funcionalidades

- ✅ **API REST** com FastAPI
- ✅ **Simulação de Lances** com validação de regras
- ✅ **Estratégias Personalizadas** para cada leilão
- ✅ **Monitoramento de Leilões** em tempo real
- 🔄 **Interface Web** (em desenvolvimento)
- 🔄 **Integração com Portais** (em desenvolvimento)

## 🚀 Instalação Rápida

### Pré-requisitos
- Python 3.8+ instalado
- Conexão com internet

### Passo a Passo

1. **Clone ou baixe o projeto**
   ```bash
   # Se usando Git
   git clone <seu-repositorio>
   cd licita-bot
   ```

2. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

3. **Inicie o servidor**
   ```bash
   python -m uvicorn main:app --reload --port 8001
   ```

4. **Acesse a API**
   - Swagger UI: http://localhost:8001/docs
   - Health Check: http://localhost:8001/health

## 📖 Como Usar

### 1. Listar Leilões Disponíveis
```bash
GET http://localhost:8001/auctions
```

### 2. Criar Estratégia de Lance
```bash
POST http://localhost:8001/strategy
{
  "name": "Estratégia Agressiva",
  "min_decrement": 50.0,
  "floor_price": 2900.0,
  "max_rounds": 10
}
```

### 3. Simular Lance
```bash
POST http://localhost:8001/bid/simulate
{
  "auction_id": 1,
  "proposed_price": 3200.0
}
```

## 🛠️ Desenvolvimento

### Estrutura do Projeto
```
licita-bot/
├── main.py              # API principal
├── requirements.txt     # Dependências
├── README.md           # Este arquivo
├── docs/               # Documentação (futuro)
├── tests/              # Testes (futuro)
└── frontend/           # Interface web (futuro)
```

### Próximas Funcionalidades
- [ ] Banco de dados SQLite
- [ ] Autenticação JWT
- [ ] Interface web React
- [ ] Integração real com portais
- [ ] Sistema de notificações
- [ ] Relatórios e dashboards

## 📞 Suporte

Para dúvidas ou sugestões, entre em contato:
- Email: seu-email@exemplo.com
- WhatsApp: (xx) xxxxx-xxxx

## 📄 Licença

Este projeto é de uso privado e comercial.

---
**Desenvolvido com ❤️ para automatizar suas licitações**