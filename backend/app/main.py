import asyncio
from contextlib import suppress

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.realtime.manager import realtime_manager
from app.services.reservation_service import get_redis, release_expired_reservations


async def reservation_expiry_loop() -> None:
    redis = get_redis()
    while True:
        await asyncio.sleep(15)
        db = SessionLocal()
        try:
            expired = release_expired_reservations(db, redis)
            if expired:
                db.commit()
                for sim in expired:
                    await realtime_manager.broadcast(
                        f"company:{sim.company_id}:numbers",
                        {
                            "type": "NUMBER_RELEASED",
                            "sim_record_id": sim.id,
                            "msisdn": sim.msisdn,
                            "status": "AVAILABLE",
                        },
                    )
            else:
                db.rollback()
        finally:
            db.close()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.project_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.on_event("startup")
    async def start_reservation_expiry_loop() -> None:
        app.state.reservation_expiry_task = asyncio.create_task(reservation_expiry_loop())

    @app.on_event("shutdown")
    async def stop_reservation_expiry_loop() -> None:
        task = getattr(app.state, "reservation_expiry_task", None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.project_name}

    @app.websocket("/ws/{channel}")
    async def websocket_endpoint(websocket: WebSocket, channel: str) -> None:
        await realtime_manager.connect(channel, websocket)
        try:
            while True:
                await websocket.receive_text()
        finally:
            realtime_manager.disconnect(channel, websocket)

    return app


app = create_app()
