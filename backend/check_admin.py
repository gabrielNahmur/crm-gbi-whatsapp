"""Verificar is_admin do usuário admin"""
import asyncio

async def check():
    from app.database.postgres import async_session
    from app.models import Agent
    from sqlalchemy import select
    
    async with async_session() as db:
        r = await db.execute(select(Agent).where(Agent.email == "gabriel.amaro@gbirs.com.br"))
        a = r.scalar_one_or_none()
        if a:
            print(f"ID: {a.id}")
            print(f"Name: {a.name}")
            print(f"Email: {a.email}")
            print(f"is_admin: {a.is_admin}")
            print(f"is_active: {a.is_active}")
        else:
            print("Usuario nao encontrado!")

if __name__ == "__main__":
    asyncio.run(check())
