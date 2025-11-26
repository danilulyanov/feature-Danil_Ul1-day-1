from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User
from bot.utils.logging import get_logger

# Create logger for this module
repo_logger = get_logger(__name__)


class UserRepository:
    """Repository for user-related database operations"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = repo_logger.bind(repository="UserRepository")

    async def get_or_create_user(self, tg_user_id: str, **kwargs) -> User:
        """Get existing user or create a new one"""
        try:
            # Try to get existing user
            stmt = select(User).where(User.tg_user_id == tg_user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                # Update user info if provided
                update_data = {}
                for k, v in kwargs.items():
                    if not hasattr(user, k) or v is None:
                        continue
                    if k in {"first_name", "last_name"} and getattr(user, k):
                        continue  # keep user-provided names
                    if k == "language_code" and getattr(user, k):
                        continue  # preserve user-selected language
                    update_data[k] = v
                if update_data:
                    update_stmt = update(User).where(User.tg_user_id == tg_user_id).values(**update_data)
                    await self.session.execute(update_stmt)
                    await self.session.commit()
                    # Refresh the user object to get updated data
                    await self.session.refresh(user)
                    self.logger.debug(f"Updated user {tg_user_id} with data: {update_data}")
                return user
            else:
                # Create new user
                user_data = {"tg_user_id": tg_user_id, **kwargs}
                user = User(**user_data)
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)
                self.logger.info(f"Created new user with ID {user.id}, tg_user_id {tg_user_id}")
                return user
        except Exception as e:
            self.logger.error(f"Error getting/creating user {tg_user_id}: {e}")
            await self.session.rollback()
            raise

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by internal ID"""
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                self.logger.debug(f"Retrieved user with ID {user_id}")
            else:
                self.logger.debug(f"User with ID {user_id} not found")
            return user
        except Exception as e:
            self.logger.error(f"Error getting user by ID {user_id}: {e}")
            raise

    async def update_user_preferences(self, tg_user_id: str, preferences: dict) -> bool:
        """Update user preferences"""
        try:
            stmt = update(User).where(User.tg_user_id == tg_user_id).values(preferences=preferences)
            result = await self.session.execute(stmt)
            await self.session.commit()

            if result.rowcount > 0:
                self.logger.info(f"Updated preferences for user {tg_user_id}")
                return True
            else:
                self.logger.warning(f"No user found to update preferences for {tg_user_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error updating preferences for user {tg_user_id}: {e}")
            await self.session.rollback()
            raise

    async def update_preferences(self, tg_user_id: str, **kwargs) -> bool:
        """Merge provided preference fields into existing preferences JSON"""
        if not kwargs:
            return True

        try:
            # Get current preferences
            stmt = select(User).where(User.tg_user_id == tg_user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                self.logger.warning(f"No user found to update preferences for {tg_user_id}")
                return False

            current = dict(user.preferences or {})
            updated = current.copy()

            for key, value in kwargs.items():
                if value is None:
                    updated.pop(key, None)
                else:
                    updated[key] = value

            if updated == current:
                self.logger.debug(f"No preference changes detected for user {tg_user_id}")
                return True

            update_stmt = update(User).where(User.tg_user_id == tg_user_id).values(preferences=updated)
            await self.session.execute(update_stmt)
            await self.session.commit()
            self.logger.info(f"Updated preferences for user {tg_user_id}: {list(kwargs.keys())}")
            return True
        except Exception as e:
            self.logger.error(f"Error merging preferences for user {tg_user_id}: {e}")
            await self.session.rollback()
            raise

    async def get_users_for_schedule(self, time_str: str) -> list[User]:
        """Return active users whose preferences.vacancy_schedule_time matches HH:MM."""
        try:
            stmt = (
                select(User)
                .where(User.is_active.is_(True))
                .where(User.preferences["vacancy_schedule_time"].as_string() == time_str)
            )
            result = await self.session.execute(stmt)
            users = list(result.scalars().all())
            self.logger.debug(f"Found {len(users)} users scheduled at {time_str}")
            return users
        except Exception as e:
            self.logger.error(f"Error fetching users for schedule {time_str}: {e}")
            return []

    async def update_language_code(self, tg_user_id: str, language_code: str) -> bool:
        try:
            stmt = update(User).where(User.tg_user_id == tg_user_id).values(language_code=language_code)
            result = await self.session.execute(stmt)
            await self.session.commit()
            if result.rowcount:
                self.logger.info(f"Updated language for user {tg_user_id} to {language_code}")
                return True
            self.logger.warning(f"No user found to update language for {tg_user_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating language for user {tg_user_id}: {e}")
            await self.session.rollback()
            raise

    async def update_user_city(self, tg_user_id: str, city: str, hh_area_id: str | None = None) -> bool:
        """Update user's city and HH.ru area ID"""
        try:
            stmt = update(User).where(User.tg_user_id == tg_user_id).values(city=city, hh_area_id=hh_area_id)
            result = await self.session.execute(stmt)
            await self.session.commit()

            if result.rowcount > 0:
                self.logger.info(f"Updated city for user {tg_user_id}: {city} (area_id: {hh_area_id})")
                return True
            else:
                self.logger.warning(f"No user found to update city for {tg_user_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error updating city for user {tg_user_id}: {e}")
            await self.session.rollback()
            raise

    async def get_user_city(self, tg_user_id: str) -> tuple[str, str | None] | None:
        """Get user's city and HH.ru area ID. Returns (city, hh_area_id) or None."""
        try:
            stmt = select(User.city, User.hh_area_id).where(User.tg_user_id == tg_user_id)
            result = await self.session.execute(stmt)
            row = result.first()
            if row and row[0]:
                return (row[0], row[1])
            return None
        except Exception as e:
            self.logger.error(f"Error getting city for user {tg_user_id}: {e}")
            return None

    async def get_user_by_tg_id(self, tg_id: str):
        stmt = select(User).where(User.tg_user_id == tg_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_user_name(
        self, tg_user_id: str, first_name: str | None = None, last_name: str | None = None
    ) -> bool:
        """Update user's first/last name"""
        if first_name is None and last_name is None:
            return True
        try:
            update_data = {}
            if first_name is not None:
                update_data["first_name"] = first_name
            if last_name is not None:
                update_data["last_name"] = last_name

            stmt = update(User).where(User.tg_user_id == tg_user_id).values(**update_data)
            result = await self.session.execute(stmt)
            await self.session.commit()

            if result.rowcount > 0:
                self.logger.info(
                    f"Updated name for user {tg_user_id}: "
                    f"{'first_name' if 'first_name' in update_data else ''} "
                    f"{'last_name' if 'last_name' in update_data else ''}"
                )
                return True
            self.logger.warning(f"No user found to update name for {tg_user_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating name for user {tg_user_id}: {e}")
            await self.session.rollback()
            raise

    async def update_search_filters(self, tg_user_id: str, **kwargs) -> bool:
        """Merge search filter fields into preferences.search_filters"""
        if not kwargs:
            return True
        try:
            stmt = select(User).where(User.tg_user_id == tg_user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                self.logger.warning(f"No user found to update search filters for {tg_user_id}")
                return False

            prefs = dict(user.preferences or {})
            filters = dict(prefs.get("search_filters") or {})

            changed = False
            for key, value in kwargs.items():
                if value is None:
                    if key in filters:
                        filters.pop(key, None)
                        changed = True
                else:
                    if filters.get(key) != value:
                        filters[key] = value
                        changed = True

            if not changed:
                self.logger.debug(f"No search filter changes for user {tg_user_id}")
                return True

            prefs["search_filters"] = filters
            await self.update_user_preferences(tg_user_id, prefs)
            return True
        except Exception as e:
            self.logger.error(f"Error updating search filters for user {tg_user_id}: {e}")
            await self.session.rollback()
            raise

    async def get_users_with_schedule(self) -> list[User]:
        """Return active users that have vacancy_schedule_time set."""
        try:
            stmt = (
                select(User)
                .where(User.is_active.is_(True))
                .where(User.preferences["vacancy_schedule_time"].isnot(None))
            )
            result = await self.session.execute(stmt)
            users = list(result.scalars().all())
            if users:
                self.logger.debug(f"Found {len(users)} users with schedule set")
            return users
        except Exception as e:
            self.logger.error(f"Error fetching users with schedule: {e}")
            return []
