import os

import uvicorn

from scripts import dev_migrate, seed


def main() -> None:
    dev_migrate.main()
    seed.main()
    uvicorn.run(
        "app.main:app",
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=os.getenv("BACKEND_RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
