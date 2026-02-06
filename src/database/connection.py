"""
Database Connection Manager - SQLite Async
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async SQLite database connection manager."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
    
    @classmethod
    async def create(cls, db_path: Path) -> "DatabaseManager":
        """Create and initialize the database manager."""
        manager = cls(db_path)
        await manager._init_db()
        return manager
    
    async def _init_db(self) -> None:
        """Initialize the database with schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with self.connection() as db:
            # Read and execute schema
            schema_path = Path(__file__).parent / "migrations" / "init_schema.sql"
            if schema_path.exists():
                schema = schema_path.read_text()
                await db.executescript(schema)
                await db.commit()
                logger.info("Database schema initialized")
            else:
                logger.warning(f"Schema file not found: {schema_path}")
            
            # Automatic Migrations
            # 1. Add is_ephemeral to songs if missing
            try:
                await db.execute("SELECT is_ephemeral FROM songs LIMIT 1")
            except Exception:
                logger.info("Migrating: Adding is_ephemeral column to songs table")
                try:
                    await db.execute("ALTER TABLE songs ADD COLUMN is_ephemeral BOOLEAN DEFAULT 0")
                    await db.commit()
                except Exception as e:
                    logger.error(f"Migration failed: {e}")
    
    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get a database connection with automatic transaction handling."""
        async with self._lock:
            if self._connection is None:
                self._connection = await aiosqlite.connect(self.db_path)
                self._connection.row_factory = aiosqlite.Row
                # Enable foreign keys
                await self._connection.execute("PRAGMA foreign_keys = ON")
            
            try:
                yield self._connection
            except Exception:
                await self._connection.rollback()
                raise
    
    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a query and return the cursor."""
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor
    
    async def fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        """Fetch a single row as a dictionary."""
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as a list of dictionaries."""
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
