"""``python -m middleware`` - run the ingestion service on port 8000
(FR-ING-1; override with MIDDLEWARE_PORT)."""

import uvicorn

from middleware.app import create_app
from middleware.settings import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
