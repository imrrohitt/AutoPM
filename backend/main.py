from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from modules.agent.router import router as agent_router
from modules.auth.router import router as auth_router
from modules.companies.router import router as company_router
from modules.github.router import router as github_router
from modules.llm.router import router as llm_router
from modules.projects.router import router as projects_router
from modules.stories.router import router as stories_router
from modules.tickets.router import router as tickets_router
from modules.users.router import router as users_router

settings = get_settings()

app = FastAPI(title="AutoPM API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = settings.API_V1_PREFIX
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(company_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(projects_router, prefix=API_PREFIX)
app.include_router(github_router, prefix=API_PREFIX)
app.include_router(llm_router, prefix=API_PREFIX)
app.include_router(stories_router, prefix=API_PREFIX)
app.include_router(tickets_router, prefix=API_PREFIX)
app.include_router(agent_router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
