"""
Script para criar conta admin master e aplicar migração is_admin.
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def run_migration():
    from sqlalchemy import text
    from app.database.postgres import engine
    
    async with engine.begin() as conn:
        # Verificar se coluna já existe
        try:
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'agents' AND column_name = 'is_admin'
            """))
            exists = result.fetchone()
        except:
            # SQLite não tem information_schema, tenta de outra forma
            try:
                await conn.execute(text("SELECT is_admin FROM agents LIMIT 1"))
                exists = True
            except:
                exists = False
        
        if not exists:
            print("Adicionando coluna is_admin...")
            await conn.execute(text("""
                ALTER TABLE agents ADD COLUMN is_admin BOOLEAN DEFAULT FALSE
            """))
            print("Coluna is_admin adicionada!")
        else:
            print("Coluna is_admin já existe.")

async def create_admin():
    from app.api.routes.auth import get_password_hash
    from app.models import Agent
    from app.database.postgres import async_session
    from sqlalchemy import select
    
    async with async_session() as db:
        # Verificar se admin já existe
        result = await db.execute(
            select(Agent).where(Agent.email == "gabriel.amaro@gbirs.com.br")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Usuário já existe (id={existing.id}). Promovendo a admin...")
            existing.is_admin = True
            await db.commit()
            print("Usuário promovido a admin!")
        else:
            print("Criando conta admin master...")
            admin = Agent(
                name="Gabriel Amaro",
                email="gabriel.amaro@gbirs.com.br",
                password_hash=get_password_hash("Gbzxn123!"),
                sector="comercial",
                is_active=True,
                is_online=False,
                is_admin=True
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            print(f"Admin criado com sucesso! ID: {admin.id}")
        
    print("\n✅ Concluído!")
    print("Email: gabriel.amaro@gbirs.com.br")
    print("Senha: Gbzxn123!")
    print("is_admin: True")

async def main():
    await run_migration()
    await create_admin()

if __name__ == "__main__":
    asyncio.run(main())
