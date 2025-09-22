from aiogram import Router

from .start import router as start_router
from .help import router as help_router
from .echo import router as echo_router
from .files import router as files_router
from .registration import router as registration_router
from .blocks import router as blocks_router
from .receive import router as receive_router
from .repair import router as repair_router
from .issue import router as issue_router
from .printing import router as printing_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(start_router)
    root.include_router(help_router)
    root.include_router(files_router)
    root.include_router(registration_router)
    root.include_router(blocks_router)
    root.include_router(receive_router)
    root.include_router(repair_router)
    root.include_router(issue_router)
    root.include_router(printing_router)
    root.include_router(echo_router)
    return root
