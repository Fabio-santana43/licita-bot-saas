from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import os, random, math, json, asyncio

# ✅ Criação da instância do FastAPI
app = FastAPI(title="LicitaBot API (MVP)", version="0.1.0")

# ✅ Configuração correta do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:5500",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/usuarios")
def listar_usuarios():
    return [
        {"id": 1, "nome": "João"},
        {"id": 2, "nome": "Maria"},
        {"id": 3, "nome": "Carlos"}
    ]
SECRET_KEY = "sua-chave-secreta-super-segura-aqui-mude-em-producao"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
class Company(BaseModel):
    id: int
    name: str
    cnpj: str
    email: str
    is_paid: bool = True
    created_at: datetime
    comprasnet_username: Optional[str] = None
    comprasnet_password: Optional[str] = None

class User(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    company_id: int
    is_active: bool = True
    created_at: datetime

class UserInDB(User):
    hashed_password: str

class UserPublic(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    company_id: int
    company_name: str
    is_active: bool
    is_admin: bool = False

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str
    company_cnpj: str
    company_email: EmailStr
    # Em modo proprietário único, este endpoint será desabilitado

class CompanyCreateRequest(BaseModel):
    company_name: str
    company_cnpj: str
    company_email: EmailStr
    comprasnet_username: str
    comprasnet_password: str
class Auction(BaseModel):
    id: int
    portal: str
    item: str
    reference_price: float
    current_price: float
    status: str
    company_id: int
    scheduled_at: Optional[datetime] = None

class BidRequest(BaseModel):
    auction_id: int
    floor_price: float
    strategy: str
    decrement: float = 0.01

class AdminBidRequest(BaseModel):
    auction_id: int
    floor_price: float
    strategy: str
    decrement: float = 0.01
    company_id: int

class BidResponse(BaseModel):
    auction_id: int
    new_bid: float
    accepted: bool
    reason: Optional[str] = None

class AutoBidRequest(BaseModel):
    auction_id: int
    floor_price: float
    strategy: str
    decrement: float = 0.01
    max_rounds: int = 10

class AutoBidResponse(BaseModel):
    auction_id: int
    final_price: float
    rounds_executed: int
    accepted_rounds: int
    stopped_reason: Optional[str] = None

class PriceRange(BaseModel):
    min_value: float
    max_value: Optional[float] = None
    min_decrement: float
    tick_size: float
    precision: int

class PortalRules(BaseModel):
    name: str
    price_ranges: List[PriceRange]
    must_be_lower: bool = True
    max_bid_attempts: int = 3
    bid_timeout_seconds: int = 300

class HistoryEvent(BaseModel):
    timestamp: str
    auction_id: int
    portal: str
    prev_price: float
    proposed: float
    accepted: bool
    strategy: Optional[str] = None
    decrement: Optional[float] = None
    floor_price: Optional[float] = None
    reason: Optional[str] = None
    route: Optional[str] = None
    round_index: Optional[int] = None
    applied_rule: Optional[str] = None
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user_by_email(email: str) -> Optional[UserInDB]:
    # Primeiro tenta no cache em memória
    user = USERS_DB.get(email)
    if user:
        return user
    # Fallback: recarrega do arquivo persistido se existir
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                raw_users = json.load(f)
            # Atualiza o cache sem remover entradas existentes
            for em, data in raw_users.items():
                if em not in USERS_DB:
                    USERS_DB[em] = UserInDB(**data)
            return USERS_DB.get(email)
    except Exception as e:
        print(f"[WARN] Falha ao recarregar usuários do arquivo: {e}")
    return None
async def get_current_user(token: str = Depends
(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(token_data.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Acesso bloqueado: conta inválida ou inativa")
    return user
COMPRASNET_RANGES = [
    PriceRange(min_value=0.0, max_value=80.0, min_decrement=0.01, tick_size=0.01, precision=2),
    PriceRange(min_value=80.01, max_value=800.0, min_decrement=0.05, tick_size=0.01, precision=2),
    PriceRange(min_value=800.01, max_value=8000.0, min_decrement=0.50, tick_size=0.01, precision=2),
    PriceRange(min_value=8000.01, max_value=80000.0, min_decrement=5.0, tick_size=0.01, precision=2),
    PriceRange(min_value=80000.01, max_value=800000.0, min_decrement=50.0, tick_size=0.01, precision=2),
    PriceRange(min_value=800000.01, max_value=None, min_decrement=500.0, tick_size=0.01, precision=2),
]

LICITACOES_E_RANGES = [
    PriceRange(min_value=0.0, max_value=1000.0, min_decrement=0.01, tick_size=0.01, precision=2),
    PriceRange(min_value=1000.01, max_value=10000.0, min_decrement=1.0, tick_size=0.01, precision=2),
    PriceRange(min_value=10000.01, max_value=None, min_decrement=10.0, tick_size=0.01, precision=2),
]
COMPANIES: Dict[int, Company] = {
    1: Company(id=1, name="TechCorp Ltda", cnpj="12.345.678/0001-90", email="contato@techcorp.com", created_at=datetime.utcnow()),
    2: Company(id=2, name="InnovaSoft SA", cnpj="98.765.432/0001-10", email="admin@innovasoft.com", created_at=datetime.utcnow()),
}

USERS_DB: Dict[str, UserInDB] = {
    "admin@techcorp.com": UserInDB(
        id=1, email="admin@techcorp.com", full_name="João Silva", company_id=1,
        is_active=True, created_at=datetime.utcnow(),
        hashed_password=pwd_context.hash("senha123")
    ),
    "maria@innovasoft.com": UserInDB(
        id=2, email="maria@innovasoft.com", full_name="Maria Santos", company_id=2,
        is_active=False, created_at=datetime.utcnow(),
        hashed_password=pwd_context.hash("senha456")
    ),
}

AUCTIONS: List[Auction] = [
    Auction(id=1, portal="Comprasnet", item="Notebook 14", reference_price=3500.00, current_price=3500.00, status="running", company_id=1),
    Auction(id=2, portal="Licitacoes-e", item="Cafeteiras industriais", reference_price=12000.00, current_price=12000.00, status="scheduled", company_id=1),
    Auction(id=3, portal="Comprasnet", item="Impressora laser", reference_price=850.00, current_price=850.00, status="running", company_id=2),
    Auction(id=4, portal="Comprasnet", item="Veículo oficial", reference_price=85000.00, current_price=85000.00, status="running", company_id=2),
]

RULES = {
    "Comprasnet": PortalRules(name="Comprasnet", price_ranges=COMPRASNET_RANGES, must_be_lower=True, max_bid_attempts=3, bid_timeout_seconds=300),
    "Licitacoes-e": PortalRules(name="Licitacoes-e", price_ranges=LICITACOES_E_RANGES, must_be_lower=True, max_bid_attempts=5, bid_timeout_seconds=180),
}

HISTORY: List[HistoryEvent] = []

# Persistência simples em disco para AUCTIONS
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
AUCTIONS_FILE = os.path.join(DATA_DIR, "auctions.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
COMPANIES_FILE = os.path.join(DATA_DIR, "companies.json")

def save_auctions() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(AUCTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump([a.model_dump() for a in AUCTIONS], f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        # Em produção, usar logging
        print(f"[WARN] Falha ao salvar auctions: {e}")

def load_auctions() -> None:
    global AUCTIONS
    try:
        if os.path.exists(AUCTIONS_FILE):
            with open(AUCTIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            AUCTIONS = [Auction(**a) for a in raw]
    except Exception as e:
        print(f"[WARN] Falha ao carregar auctions: {e}")

# Carrega dados persistidos (se existirem) na inicialização
load_auctions()

def save_history() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([h.model_dump() for h in HISTORY], f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"[WARN] Falha ao salvar histórico: {e}")

def load_history() -> None:
    global HISTORY
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            HISTORY = [HistoryEvent(**h) for h in raw]
    except Exception as e:
        print(f"[WARN] Falha ao carregar histórico: {e}")

def append_history(event: HistoryEvent) -> None:
    HISTORY.append(event)
    save_history()

# Carrega histórico persistido
load_history()

# Persistência de usuários e empresas
def save_users_companies() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({email: user.model_dump() for email, user in USERS_DB.items()}, f, ensure_ascii=False, indent=2, default=str)
        with open(COMPANIES_FILE, "w", encoding="utf-8") as f:
            json.dump({str(cid): comp.model_dump() for cid, comp in COMPANIES.items()}, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"[WARN] Falha ao salvar usuários/empresas: {e}")

def load_users_companies() -> None:
    global USERS_DB, COMPANIES
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                raw_users = json.load(f)
            USERS_DB = {email: UserInDB(**data) for email, data in raw_users.items()}
        if os.path.exists(COMPANIES_FILE):
            with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
                raw_companies = json.load(f)
            COMPANIES = {int(cid): Company(**data) for cid, data in raw_companies.items()}
    except Exception as e:
        print(f"[WARN] Falha ao carregar usuários/empresas: {e}")

# Carrega usuários/empresas persistidos (se existirem) na inicialização
load_users_companies()

# Conexões WebSocket por leilão
WS_CONNECTIONS: Dict[int, List[WebSocket]] = {}

def _register_ws(auction_id: int, ws: WebSocket):
    WS_CONNECTIONS.setdefault(auction_id, []).append(ws)

def _unregister_ws(auction_id: int, ws: WebSocket):
    conns = WS_CONNECTIONS.get(auction_id, [])
    WS_CONNECTIONS[auction_id] = [c for c in conns if c is not ws]

async def broadcast_auction_update(auction: Auction, event: str, extra: Optional[dict] = None):
    payload = {
        "event": event,
        "auction": auction.model_dump(),
    }
    if extra:
        payload.update(extra)
    for ws in WS_CONNECTIONS.get(auction.id, []):
        try:
            await ws.send_json(payload)
        except RuntimeError:
            # Ignora conexões que não aceitam envio
            pass

def get_user_from_token(raw_token: str) -> Optional[UserInDB]:
    try:
        payload = jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        user = get_user_by_email(email)
        return user
    except Exception:
        return None

@app.websocket("/ws/auction/{auction_id}")
async def ws_auction_endpoint(websocket: WebSocket, auction_id: int):
    # Aceita token via query param (?token=)
    token_q = websocket.query_params.get("token")
    await websocket.accept()
    user = get_user_from_token(token_q) if token_q else None
    auction = next((a for a in AUCTIONS if a.id == auction_id), None)
    if not auction:
        await websocket.send_json({"event": "error", "message": "Leilão não encontrado"})
        await websocket.close(code=4000)
        return
    if not user or (auction.company_id != user.company_id):
        await websocket.send_json({"event": "error", "message": "Acesso negado"})
        await websocket.close(code=4001)
        return
    # Registra conexão e envia estado inicial
    _register_ws(auction_id, websocket)
    try:
        await websocket.send_json({"event": "init", "auction": auction.model_dump()})
        while True:
            # Mantém conexão (podemos lidar com pings no futuro)
            _ = await websocket.receive_text()
            # Opcional: ignorar mensagens ou implementar comandos
    except WebSocketDisconnect:
        _unregister_ws(auction_id, websocket)
@app.get("/")
def root():
    return {"message": "LicitaBot API está rodando!"}

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
@app.post("/auth/signup", response_model=UserPublic, tags=["Autenticação"], summary="Cadastrar usuário e empresa")
def signup(request: SignUpRequest):
    # Cadastro público desabilitado: o sistema é operado apenas pelo proprietário.
    raise HTTPException(status_code=403, detail="Cadastro público desabilitado. Use o Painel Admin para criar clientes.")
@app.post("/auth/login", response_model=Token, tags=["Autenticação"], summary="Autenticar e obter token JWT")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Acesso bloqueado: conta inadimplente. Contate o suporte.")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}
@app.get("/me", response_model=UserPublic, tags=["Autenticação"], summary="Informações do usuário autenticado")
async def get_me(current_user: UserInDB = Depends(get_current_user)):
    company = COMPANIES.get(current_user.company_id)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@techcorp.com")
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        company_id=current_user.company_id,
        company_name=company.name if company else "Empresa não encontrada",
        is_active=current_user.is_active,
        is_admin=(current_user.email == admin_email)
    )
@app.get("/auctions", response_model=List[Auction])
def list_auctions(status: Optional[str] = None, current_user: UserInDB = Depends(get_current_user)):
    user_auctions = [a for a in AUCTIONS if a.company_id == current_user.company_id]
    if status:
        return [a for a in user_auctions if a.status == status]
    return user_auctions

@app.get("/auctions/{auction_id}", response_model=Auction)
def get_auction(auction_id: int, current_user: UserInDB = Depends(get_current_user)):
    auction = next((a for a in AUCTIONS if a.id == auction_id), None)
    if not auction:
        raise HTTPException(status_code=404, detail="Leilão não encontrado")
    if auction.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Acesso negado: leilão não pertence à sua empresa")
    return auction
@app.get("/history/{auction_id}", response_model=List[HistoryEvent])
def get_history(auction_id: int, current_user: UserInDB = Depends(get_current_user)):
    auction = next((a for a in AUCTIONS if a.id == auction_id), None)
    if not auction:
        raise HTTPException(status_code=404, detail="Leilão não encontrado")
    if auction.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Acesso negado: leilão não pertence à sua empresa")
    return [h for h in HISTORY if h.auction_id == auction_id]
def get_price_range_rule(portal_name: str, price: float) -> Tuple[PriceRange, str]:
    portal_rules = RULES.get(portal_name)
    if not portal_rules:
        default_range = PriceRange(min_value=0.0, max_value=None, min_decrement=0.01, tick_size=0.01, precision=2)
        return default_range, "Regra padrão"
    for range_rule in portal_rules.price_ranges:
        if price >= range_rule.min_value:
            if range_rule.max_value is None or price <= range_rule.max_value:
                desc = f"R$ {range_rule.min_value:.2f}"
                if range_rule.max_value:
                    desc += f" - R$ {range_rule.max_value:.2f}"
                else:
                    desc += " ou mais"
                return range_rule, desc
    return portal_rules.price_ranges[0], "Faixa padrão"
def adjust_decrement(strategy: str, decrement: float, base_min_decrement: float) -> float:
    if strategy == "agressivo":
        adjusted = decrement * 3
    elif strategy == "conservador":
        adjusted = decrement * 0.5
    else:
        adjusted = decrement
    return max(adjusted, base_min_decrement)
@app.get("/strategies")
def list_strategies():
    return [
        {"name": "incremental", "desc": "Reduz pequenos valores com proteção de margem"},
        {"name": "agressivo", "desc": "Reage em frações de segundo com redução maior"},
        {"name": "conservador", "desc": "Lances espaçados com foco em margem"},
    ]
@app.get("/rules", response_model=List[PortalRules])
def list_rules():
    return list(RULES.values())

@app.get("/rules/{portal}", response_model=PortalRules)
def get_rules(portal: str):
    rules = RULES.get(portal)
    if not rules:
        raise HTTPException(status_code=404, detail="Portal não encontrado")
    return rules

@app.get("/rules/{portal}/price/{price}")
def get_price_rule(portal: str, price: float):
    if portal not in RULES:
        raise HTTPException(status_code=404, detail="Portal não encontrado")
    range_rule, range_desc = get_price_range_rule(portal, price)
    return {
        "portal": portal,
        "price": price,
        "range_description": range_desc,
        "min_decrement": range_rule.min_decrement,
        "tick_size": range_rule.tick_size,
        "precision": range_rule.precision,
        "example_valid_decrements": [
            range_rule.min_decrement,
            range_rule.min_decrement * 2,
            range_rule.min_decrement * 5,
            range_rule.min_decrement * 10
        ]
    }
@app.post("/auctions/{auction_id}/reset", response_model=Auction)
def reset_auction(auction_id: int, current_user: UserInDB = Depends(get_current_user)):
    auction = next((a for a in AUCTIONS if a.id == auction_id), None)
    if not auction:
        raise HTTPException(status_code=404, detail="Leilão não encontrado")
    if auction.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Acesso negado: leilão não pertence à sua empresa")
    prev = auction.current_price
    auction.current_price = auction.reference_price
    range_rule, range_desc = get_price_range_rule(auction.portal, auction.reference_price)
    append_history(HistoryEvent(
        timestamp=datetime.utcnow().isoformat(),
        auction_id=auction.id,
        portal=auction.portal,
        prev_price=prev,
        proposed=auction.reference_price,
        accepted=True,
        strategy="reset",
        decrement=0.0,
        floor_price=None,
        reason="Reset para preço de referência",
        route="reset",
        round_index=None,
        applied_rule=range_desc,
    ))
    # Persistir alteração de preço
    save_auctions()
    # Notificar via WebSocket
    try:
        asyncio.create_task(broadcast_auction_update(auction, "reset"))
    except Exception:
        pass
    return auction
@app.post("/bid", response_model=BidResponse)
def place_bid(req: BidRequest, current_user: UserInDB = Depends(get_current_user)):
    auction = next((a for a in AUCTIONS if a.id == req.auction_id), None)
    if not auction or auction.status != "running":
        event = HistoryEvent(
            timestamp=datetime.utcnow().isoformat(),
            auction_id=req.auction_id,
            portal=auction.portal if auction else "?",
            prev_price=auction.current_price if auction else 0.0,
            proposed=0.0,
            accepted=False,
            strategy=req.strategy,
            decrement=req.decrement,
            floor_price=req.floor_price,
            reason="Leilão não encontrado ou não está em execução",
            route="manual",
            applied_rule="N/A"
        )
        append_history(event)
        # Notificar rejeição
        try:
            if auction:
                asyncio.create_task(broadcast_auction_update(auction, "bid_rejected", {"history": event.model_dump()}))
        except Exception:
            pass
        return BidResponse(auction_id=req.auction_id, new_bid=0.0, accepted=False, reason="Leilão não está em execução")
    if auction.company_id != current_user.company_id:
        event = HistoryEvent(
            timestamp=datetime.utcnow().isoformat(),
            auction_id=req.auction_id,
            portal=auction.portal,
            prev_price=auction.current_price,
            proposed=0.0,
            accepted=False,
            strategy=req.strategy,
            decrement=req.decrement,
            floor_price=req.floor_price,
            reason="Acesso negado: leilão não pertence à sua empresa",
            route="manual",
            applied_rule="N/A"
        )
        append_history(event)
        try:
            asyncio.create_task(broadcast_auction_update(auction, "bid_rejected", {"history": event.model_dump()}))
        except Exception:
            pass
        return BidResponse(auction_id=req.auction_id, new_bid=auction.current_price, accepted=False, reason="Acesso negado")
    range_rule, range_desc = get_price_range_rule(auction.portal, auction.current_price)
    dec = adjust_decrement(req.strategy, req.decrement, range_rule.min_decrement)
    proposed = round(auction.current_price - dec, range_rule.precision)
    if dec < range_rule.min_decrement or proposed >= auction.current_price or proposed < req.floor_price:
        reason = "Decremento inválido ou abaixo do piso"
        event = HistoryEvent(
            timestamp=datetime.utcnow().isoformat(),
            auction_id=req.auction_id,
            portal=auction.portal,
            prev_price=auction.current_price,
            proposed=proposed,
            accepted=False,
            strategy=req.strategy,
            decrement=dec,
            floor_price=req.floor_price,
            reason=reason,
            route="manual",
            applied_rule=range_desc
        )
        append_history(event)
        try:
            asyncio.create_task(broadcast_auction_update(auction, "bid_rejected", {"history": event.model_dump()}))
        except Exception:
            pass
        return BidResponse(auction_id=req.auction_id, new_bid=auction.current_price, accepted=False, reason=reason)
    prev = auction.current_price
    auction.current_price = proposed
    event = HistoryEvent(
        timestamp=datetime.utcnow().isoformat(),
        auction_id=req.auction_id,
        portal=auction.portal,
        prev_price=prev,
        proposed=proposed,
        accepted=True,
        strategy=req.strategy,
        decrement=dec,
        floor_price=req.floor_price,
        reason=None,
        route="manual",
        applied_rule=range_desc
    )
    append_history(event)
    # Persistir alteração após lance
    save_auctions()
    # Notificar via WebSocket
    try:
        asyncio.create_task(broadcast_auction_update(auction, "bid_accepted", {"history": event.model_dump()}))
    except Exception:
        pass
    return BidResponse(auction_id=req.auction_id, new_bid=proposed, accepted=True)
class SyncLicitacoesResponse(BaseModel):
    total_encontradas: int
    novas_adicionadas: int
    licitacoes: List[dict]
    message: str
@app.options("/sync/licitacoes")
def options_sync(request: Request):
    allowed = {"http://127.0.0.1:8002", "http://localhost:8002"}
    origin = request.headers.get("origin")
    headers = {}
    if origin in allowed:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        }
    return JSONResponse(content={"ok": True}, headers=headers)
@app.post("/sync/licitacoes", response_model=SyncLicitacoesResponse, summary="Sincronizar Licitações", tags=["Sincronização"])
def sync_licitacoes_portal_transparencia(request: Request, current_user: UserInDB = Depends(get_current_user)):
    company = COMPANIES.get(current_user.company_id)
    cnpj_empresa = company.cnpj if company else "N/A"
    licitacoes_simuladas = [
        {
            "numero": f"PE{random.randint(100, 999)}/2025",
            "objeto": "Aquisição de equipamentos de informática",
            "orgao": "Ministério da Educação",
            "valor_estimado": random.uniform(50000, 500000),
            "data_abertura": (datetime.now() + timedelta(days=random.randint(1, 30))).isoformat(),
            "modalidade": "Pregão Eletrônico",
            "situacao": "Aberto",
            "portal": "Comprasnet"
        },
        {
            "numero": f"CC{random.randint(100, 999)}/2025",
            "objeto": "Prestação de serviços de manutenção predial",
            "orgao": "Prefeitura Municipal",
            "valor_estimado": random.uniform(100000, 800000),
            "data_abertura": (datetime.now() + timedelta(days=random.randint(1, 45))).isoformat(),
            "modalidade": "Concorrência",
            "situacao": "Aberto",
            "portal": "Comprasnet"
        },
        {
            "numero": f"TP{random.randint(100, 999)}/2025",
            "objeto": "Fornecimento de materiais de escritório",
            "orgao": "Secretaria de Administração",
            "valor_estimado": random.uniform(20000, 150000),
            "data_abertura": (datetime.now() + timedelta(days=random.randint(1, 20))).isoformat(),
            "modalidade": "Tomada de Preços",
            "situacao": "Aberto",
            "portal": "Comprasnet"
        }
    ]
    licitacoes_existentes = {a.item for a in AUCTIONS if a.company_id == current_user.company_id}
    novas_licitacoes = [lic for lic in licitacoes_simuladas if lic["objeto"] not in licitacoes_existentes]
    novas_adicionadas = 0
    for lic in novas_licitacoes:
        novo_id = max([a.id for a in AUCTIONS], default=0) + 1
        nova_licitacao = Auction(
            id=novo_id,
            company_id=current_user.company_id,
            portal=lic["portal"],
            item=lic["objeto"],
            reference_price=lic["valor_estimado"],
            current_price=lic["valor_estimado"],
            status="running"
        )
        AUCTIONS.append(nova_licitacao)
        novas_adicionadas += 1
    # Persistir novas licitações adicionadas via sync
    if novas_adicionadas > 0:
        save_auctions()
    response_obj = SyncLicitacoesResponse(
        total_encontradas=len(licitacoes_simuladas),
        novas_adicionadas=novas_adicionadas,
        licitacoes=licitacoes_simuladas,
        message=f"Sincronização concluída! {novas_adicionadas} novas licitações adicionadas para a empresa {(company.name if company else 'Empresa')} (CNPJ: {cnpj_empresa})"
    )
    allowed = {"http://127.0.0.1:8002", "http://localhost:8002"}
    origin = request.headers.get("origin")
    headers = {}
    if origin in allowed:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Expose-Headers": "*",
        }
    return JSONResponse(content=response_obj.model_dump(), headers=headers)
class AdminUser(BaseModel):
    email: EmailStr
    full_name: str
    company_name: str
    company_paid: bool
    is_active: bool
    created_at: datetime

class AdminCompany(BaseModel):
    id: int
    name: str
    cnpj: str
    email: str
    is_paid: bool
    created_at: datetime

class PaymentUpdateRequest(BaseModel):
    is_paid: bool

def _require_admin(request: Request):
    """Exige autenticação de administrador via JWT Bearer.

    O administrador é identificado pelo email configurado em ADMIN_EMAIL
    (padrão: "admin@techcorp.com"). Remove o uso do cabeçalho X-Admin-Key.
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@techcorp.com")
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autorizado: faça login como administrador")
    raw_token = auth_header.split(" ", 1)[1]
    user = get_user_from_token(raw_token)
    if not user or user.email != admin_email:
        raise HTTPException(status_code=403, detail="Acesso negado: não é administrador")

@app.get("/admin/auctions", response_model=List[Auction], tags=["Admin"], summary="Listar leilões por empresa (Admin)")
def admin_list_auctions(request: Request, company_id: Optional[int] = None, status: Optional[str] = None):
    _require_admin(request)
    auctions = AUCTIONS
    if company_id is not None:
        auctions = [a for a in auctions if a.company_id == company_id]
    if status:
        auctions = [a for a in auctions if a.status == status]
    return auctions

@app.get("/admin/auctions/{auction_id}", response_model=Auction, tags=["Admin"], summary="Detalhar leilão (Admin)")
def admin_get_auction(auction_id: int, request: Request):
    _require_admin(request)
    auction = next((a for a in AUCTIONS if a.id == auction_id), None)
    if not auction:
        raise HTTPException(status_code=404, detail="Leilão não encontrado")
    return auction

@app.get("/admin/history/{auction_id}", response_model=List[HistoryEvent], tags=["Admin"], summary="Histórico do leilão (Admin)")
def admin_get_history(auction_id: int, request: Request):
    _require_admin(request)
    auction = next((a for a in AUCTIONS if a.id == auction_id), None)
    if not auction:
        raise HTTPException(status_code=404, detail="Leilão não encontrado")
    return [h for h in HISTORY if h.auction_id == auction_id]

@app.post("/admin/auctions/{auction_id}/reset", response_model=Auction, tags=["Admin"], summary="Resetar leilão (Admin)")
def admin_reset_auction(auction_id: int, request: Request):
    _require_admin(request)
    auction = next((a for a in AUCTIONS if a.id == auction_id), None)
    if not auction:
        raise HTTPException(status_code=404, detail="Leilão não encontrado")
    prev = auction.current_price
    auction.current_price = auction.reference_price
    range_rule, range_desc = get_price_range_rule(auction.portal, auction.reference_price)
    append_history(HistoryEvent(
        timestamp=datetime.utcnow().isoformat(),
        auction_id=auction.id,
        portal=auction.portal,
        prev_price=prev,
        proposed=auction.reference_price,
        accepted=True,
        strategy="reset",
        decrement=0.0,
        floor_price=None,
        reason="Reset (Admin) para preço de referência",
        route="admin_reset",
        round_index=None,
        applied_rule=range_desc,
    ))
    save_auctions()
    try:
        asyncio.create_task(broadcast_auction_update(auction, "reset"))
    except Exception:
        pass
    return auction

@app.post("/admin/bid", response_model=BidResponse, tags=["Admin"], summary="Enviar lance em nome da empresa (Admin)")
def admin_place_bid(req: AdminBidRequest, request: Request):
    _require_admin(request)
    auction = next((a for a in AUCTIONS if a.id == req.auction_id), None)
    if not auction or auction.status != "running":
        event = HistoryEvent(
            timestamp=datetime.utcnow().isoformat(),
            auction_id=req.auction_id,
            portal=auction.portal if auction else "?",
            prev_price=auction.current_price if auction else 0.0,
            proposed=0.0,
            accepted=False,
            strategy=req.strategy,
            decrement=req.decrement,
            floor_price=req.floor_price,
            reason="Leilão não encontrado ou não está em execução",
            route="admin_manual",
            applied_rule="N/A"
        )
        append_history(event)
        try:
            if auction:
                asyncio.create_task(broadcast_auction_update(auction, "bid_rejected", {"history": event.model_dump()}))
        except Exception:
            pass
        return BidResponse(auction_id=req.auction_id, new_bid=0.0, accepted=False, reason="Leilão não está em execução")
    if auction.company_id != req.company_id:
        event = HistoryEvent(
            timestamp=datetime.utcnow().isoformat(),
            auction_id=req.auction_id,
            portal=auction.portal,
            prev_price=auction.current_price,
            proposed=0.0,
            accepted=False,
            strategy=req.strategy,
            decrement=req.decrement,
            floor_price=req.floor_price,
            reason="Leilão não pertence à empresa selecionada",
            route="admin_manual",
            applied_rule="N/A"
        )
        append_history(event)
        try:
            asyncio.create_task(broadcast_auction_update(auction, "bid_rejected", {"history": event.model_dump()}))
        except Exception:
            pass
        return BidResponse(auction_id=req.auction_id, new_bid=auction.current_price, accepted=False, reason="Acesso negado")
    range_rule, range_desc = get_price_range_rule(auction.portal, auction.current_price)
    dec = adjust_decrement(req.strategy, req.decrement, range_rule.min_decrement)
    proposed = round(auction.current_price - dec, range_rule.precision)
    if dec < range_rule.min_decrement or proposed >= auction.current_price or proposed < req.floor_price:
        reason = "Decremento inválido ou abaixo do piso"
        event = HistoryEvent(
            timestamp=datetime.utcnow().isoformat(),
            auction_id=req.auction_id,
            portal=auction.portal,
            prev_price=auction.current_price,
            proposed=proposed,
            accepted=False,
            strategy=req.strategy,
            decrement=dec,
            floor_price=req.floor_price,
            reason=reason,
            route="admin_manual",
            applied_rule=range_desc
        )
        append_history(event)
        try:
            asyncio.create_task(broadcast_auction_update(auction, "bid_rejected", {"history": event.model_dump()}))
        except Exception:
            pass
        return BidResponse(auction_id=req.auction_id, new_bid=auction.current_price, accepted=False, reason=reason)
    prev = auction.current_price
    auction.current_price = proposed
    event = HistoryEvent(
        timestamp=datetime.utcnow().isoformat(),
        auction_id=req.auction_id,
        portal=auction.portal,
        prev_price=prev,
        proposed=proposed,
        accepted=True,
        strategy=req.strategy,
        decrement=dec,
        floor_price=req.floor_price,
        reason=None,
        route="admin_manual",
        applied_rule=range_desc
    )
    append_history(event)
    save_auctions()
    try:
        asyncio.create_task(broadcast_auction_update(auction, "bid_accepted", {"history": event.model_dump()}))
    except Exception:
        pass
    return BidResponse(auction_id=req.auction_id, new_bid=proposed, accepted=True)

@app.post("/admin/companies/{company_id}/payment", response_model=AdminCompany, tags=["Admin"], summary="Atualizar status de pagamento da empresa (Admin)")
def admin_company_payment(company_id: int, payload: PaymentUpdateRequest, request: Request):
    _require_admin(request)
    company = COMPANIES.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    company.is_paid = bool(payload.is_paid)
    # Atualiza status de usuários da empresa conforme pagamento
    for u in USERS_DB.values():
        if u.company_id == company_id:
            u.is_active = bool(payload.is_paid)
    save_users_companies()
    return AdminCompany(
        id=company.id,
        name=company.name,
        cnpj=company.cnpj,
        email=company.email,
        is_paid=company.is_paid,
        created_at=company.created_at,
    )

@app.delete("/admin/companies/{company_id}", tags=["Admin"], summary="Excluir empresa e dados relacionados (Admin)")
def admin_delete_company(company_id: int, request: Request):
    _require_admin(request)
    company = COMPANIES.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    # Remover usuários da empresa
    remove_emails: List[str] = []
    for email, user in list(USERS_DB.items()):
        if user.company_id == company_id:
            remove_emails.append(email)
            del USERS_DB[email]
    # Remover leilões da empresa
    removed_auctions_ids: List[int] = [a.id for a in AUCTIONS if a.company_id == company_id]
    if removed_auctions_ids:
        # Filtra AUCTIONS
        remaining = [a for a in AUCTIONS if a.company_id != company_id]
        AUCTIONS.clear()
        AUCTIONS.extend(remaining)
    # Remover histórico dos leilões da empresa
    if removed_auctions_ids:
        remaining_hist = [h for h in HISTORY if h.auction_id not in removed_auctions_ids]
        HISTORY.clear()
        HISTORY.extend(remaining_hist)
    # Remover empresa
    del COMPANIES[company_id]
    # Persistir alterações
    save_users_companies()
    save_auctions()
    save_history()
    return {
        "message": "Empresa e dados relacionados excluídos",
        "company_id": company_id,
        "users_removed": len(remove_emails),
        "auctions_removed": len(removed_auctions_ids),
        "history_entries_removed": len([h for h in HISTORY if h.auction_id in removed_auctions_ids])
    }
@app.get("/admin/users", response_model=List[AdminUser], tags=["Admin"], summary="Listar usuários (Admin)")
def admin_list_users(request: Request):
    _require_admin(request)
    items: List[AdminUser] = []
    for u in USERS_DB.values():
        company = COMPANIES.get(u.company_id)
        items.append(AdminUser(
            email=u.email,
            full_name=u.full_name,
            company_name=(company.name if company else ""),
            company_paid=(company.is_paid if company else False),
            is_active=u.is_active,
            created_at=u.created_at,
        ))
    return items
@app.post("/admin/users/{email}/block", response_model=AdminUser, tags=["Admin"], summary="Bloquear usuário")
def admin_block_user(email: EmailStr, request: Request):
    _require_admin(request)
    user = USERS_DB.get(email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.is_active = False
    # Persistir alteração de status de usuário
    save_users_companies()
    company = COMPANIES.get(user.company_id)
    return AdminUser(
        email=user.email,
        full_name=user.full_name,
        company_name=(company.name if company else ""),
        company_paid=(company.is_paid if company else False),
        is_active=user.is_active,
        created_at=user.created_at,
    )
@app.post("/admin/users/{email}/unblock", response_model=AdminUser, tags=["Admin"], summary="Desbloquear usuário")
def admin_unblock_user(email: EmailStr, request: Request):
    _require_admin(request)
    user = USERS_DB.get(email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.is_active = True
    # Persistir alteração de status de usuário
    save_users_companies()
    company = COMPANIES.get(user.company_id)
    return AdminUser(
        email=user.email,
        full_name=user.full_name,
        company_name=(company.name if company else ""),
        company_paid=(company.is_paid if company else False),
        is_active=user.is_active,
        created_at=user.created_at,
    )


@app.post("/admin/users/{email}/payment", response_model=AdminUser, tags=["Admin"], summary="Atualizar status de pagamento da empresa e bloquear/desbloquear usuário")
def admin_update_payment(email: EmailStr, payload: PaymentUpdateRequest, request: Request):
    _require_admin(request)
    user = USERS_DB.get(email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    company = COMPANIES.get(user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    company.is_paid = payload.is_paid
    # Bloqueia automaticamente usuário se empresa está inadimplente; libera se está paga
    user.is_active = bool(payload.is_paid)
    # Persistir alteração de pagamento e status de usuário
    save_users_companies()
    return AdminUser(
        email=user.email,
        full_name=user.full_name,
        company_name=(company.name if company else ""),
        company_paid=company.is_paid,
        is_active=user.is_active,
        created_at=user.created_at,
    )

class AdminImportRequest(BaseModel):
    email: Optional[EmailStr] = None
    cnpj: Optional[str] = None
    quantity: int = 3
    portal: str = "Comprasnet"

@app.post("/admin/auctions/import", tags=["Admin"], summary="Importar licitações para um cliente por email ou CNPJ")
def admin_import_auctions(req: AdminImportRequest, request: Request):
    _require_admin(request)
    # Resolve empresa via email do usuário ou CNPJ
    company = None
    if req.email:
        user = USERS_DB.get(req.email)
        if user:
            company = COMPANIES.get(user.company_id)
    if not company and req.cnpj:
        normalized = ''.join(ch for ch in req.cnpj if ch.isdigit())
        for c in COMPANIES.values():
            cnpj_clean = ''.join(ch for ch in c.cnpj if ch.isdigit())
            if cnpj_clean == normalized:
                company = c
                break
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada por email ou CNPJ")

    # Cria licitações simuladas para a empresa
    created = []
    base_id = max([a.id for a in AUCTIONS], default=0) + 1
    samples = [
        ("Aquisição de Equipamentos de TI", 120000.0, "running"),
        ("Serviços de Manutenção Predial", 45000.0, "scheduled"),
        ("Fornecimento de Material Hospitalar", 300000.0, "scheduled"),
        ("Prestação de Serviços de Segurança", 95000.0, "running"),
    ]
    for i in range(max(1, req.quantity)):
        item, price, status_s = samples[i % len(samples)]
        auction = Auction(
            id=base_id + i,
            portal=req.portal,
            company_id=company.id,
            item=item,
            reference_price=price,
            current_price=price,
            status=status_s,
        )
        AUCTIONS.append(auction)
        created.append(auction)

    # Persistir licitações importadas pelo admin
    if created:
        save_auctions()

    return {
        "message": f"{len(created)} licitações importadas para {company.name} ({company.cnpj})",
        "created": [a.model_dump() for a in created],
    }

@app.post("/admin/users/create", response_model=AdminUser, tags=["Admin"], summary="Criar usuário e empresa (Admin)")
def admin_create_user(request_http: Request, request: SignUpRequest):
    _require_admin(request_http)
    if request.email in USERS_DB:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    company_id = max(COMPANIES.keys()) + 1 if COMPANIES else 1
    new_company = Company(
        id=company_id,
        name=request.company_name,
        cnpj=request.company_cnpj,
        email=request.company_email,
        is_paid=True,
        created_at=datetime.utcnow()
    )
    COMPANIES[company_id] = new_company
    user_id = max([u.id for u in USERS_DB.values()], default=0) + 1
    hashed_password = get_password_hash(request.password)
    new_user = UserInDB(
        id=user_id,
        email=request.email,
        full_name=request.full_name,
        company_id=company_id,
        is_active=True,
        created_at=datetime.utcnow(),
        hashed_password=hashed_password
    )
    USERS_DB[request.email] = new_user
    # Persistir novo usuário e empresa criados pelo admin
    save_users_companies()
    return AdminUser(
        email=new_user.email,
        full_name=new_user.full_name,
        company_name=new_company.name,
        company_paid=new_company.is_paid,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
    )

@app.get("/admin/companies", response_model=List[AdminCompany], tags=["Admin"], summary="Listar empresas (Admin)")
def admin_list_companies(request: Request):
    _require_admin(request)
    items: List[AdminCompany] = []
    for c in COMPANIES.values():
        items.append(AdminCompany(
            id=c.id,
            name=c.name,
            cnpj=c.cnpj,
            email=c.email,
            is_paid=c.is_paid,
            created_at=c.created_at,
        ))
    return items

@app.post("/admin/companies/create", response_model=AdminCompany, tags=["Admin"], summary="Criar empresa e credenciais do Comprasnet (Admin)")
def admin_create_company(request_http: Request, req: CompanyCreateRequest):
    _require_admin(request_http)
    # Verificar duplicidade de CNPJ
    normalized = ''.join(ch for ch in req.company_cnpj if ch.isdigit())
    for c in COMPANIES.values():
        cnpj_clean = ''.join(ch for ch in c.cnpj if ch.isdigit())
        if cnpj_clean == normalized:
            raise HTTPException(status_code=400, detail="Empresa já cadastrada para este CNPJ")
    company_id = max(COMPANIES.keys(), default=0) + 1
    new_company = Company(
        id=company_id,
        name=req.company_name,
        cnpj=req.company_cnpj,
        email=req.company_email,
        is_paid=True,
        created_at=datetime.utcnow(),
        comprasnet_username=req.comprasnet_username,
        comprasnet_password=req.comprasnet_password,
    )
    COMPANIES[company_id] = new_company
    # Cria usuário padrão para a empresa utilizando o email da empresa
    try:
        default_password = "cliente123"  # senha temporária padrão
        user_id = max([u.id for u in USERS_DB.values()], default=0) + 1
        if req.company_email not in USERS_DB:
            new_user = UserInDB(
                id=user_id,
                email=req.company_email,
                full_name=f"Contato {req.company_name}",
                company_id=company_id,
                is_active=True,
                created_at=datetime.utcnow(),
                hashed_password=get_password_hash(default_password)
            )
            USERS_DB[req.company_email] = new_user
    except Exception as e:
        print(f"[WARN] Falha ao criar usuário padrão da empresa: {e}")
    # Persistir alterações
    save_users_companies()
    return AdminCompany(
        id=new_company.id,
        name=new_company.name,
        cnpj=new_company.cnpj,
        email=new_company.email,
        is_paid=new_company.is_paid,
        created_at=new_company.created_at,
    )

@app.post("/admin/companies/{company_id}/payment", response_model=AdminCompany, tags=["Admin"], summary="Atualizar pagamento da empresa e bloquear/desbloquear usuários")
def admin_update_company_payment(company_id: int, payload: PaymentUpdateRequest, request: Request):
    _require_admin(request)
    company = COMPANIES.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    company.is_paid = payload.is_paid
    # Atualiza status de usuários da empresa conforme pagamento
    for u in USERS_DB.values():
        if u.company_id == company_id:
            u.is_active = bool(payload.is_paid)
    # Persistir alterações
    save_users_companies()
    return AdminCompany(
        id=company.id,
        name=company.name,
        cnpj=company.cnpj,
        email=company.email,
        is_paid=company.is_paid,
        created_at=company.created_at,
    )
