from app.services.marzban_service import MarzbanService
import logging

logger = logging.getLogger(__name__)

_marzban_instance: MarzbanService | None = None


async def get_marzban() -> MarzbanService:
    """Get or create singleton Marzban Service instance."""
    global _marzban_instance
    if _marzban_instance is None:
        _marzban_instance = MarzbanService()
        logger.info("Created singleton Marzban Service instance")
    return _marzban_instance


async def close_marzban():
    """Close singleton Marzban Service instance."""
    global _marzban_instance
    if _marzban_instance:
        await _marzban_instance.close()
        _marzban_instance = None
        logger.info("Closed singleton Marzban Service instance")