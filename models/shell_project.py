"""
Модель проекта Shell (основной список проектов в схеме).
MVP + OOP: каждый проект — свой префикс линка и набор дашбордов.
"""
from typing import Optional, List, Dict, Any
from models.database import DatabaseModel


class ShellProject:
    """Проект shell: slug, название, список ID дашбордов."""

    def __init__(
        self,
        id: int,
        slug: str,
        name: str,
        description: Optional[str] = None,
        dashboard_ids: Optional[str] = None,
        sort_order: int = 0,
        is_active: str = "Y",
        created_at: Optional[Any] = None,
        updated_at: Optional[Any] = None,
    ):
        self.id = id
        self.slug = slug
        self.name = name
        self.description = description or ""
        self.dashboard_ids = dashboard_ids or ""
        self.sort_order = sort_order
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def dashboard_id_list(self) -> List[str]:
        """Список ID дашбордов (из строки через запятую)."""
        if not self.dashboard_ids or not self.dashboard_ids.strip():
            return []
        return [x.strip() for x in self.dashboard_ids.split(",") if x.strip()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "dashboard_ids": self.dashboard_ids,
            "dashboard_id_list": self.dashboard_id_list,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }

    @classmethod
    def get_all(cls, active_only: bool = True) -> List["ShellProject"]:
        """Список всех проектов из таблицы UNA_SHELL_PROJECTS."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT ID, SLUG, NAME, DESCRIPTION, DASHBOARD_IDS, SORT_ORDER, IS_ACTIVE, CREATED_AT, UPDATED_AT
                    FROM UNA_SHELL_PROJECTS
                """
                if active_only:
                    sql += " WHERE IS_ACTIVE = 'Y'"
                sql += " ORDER BY SORT_ORDER, SLUG"
                out = db.execute_query(sql)
                if not out.get("success") or not out.get("data"):
                    return []
                projects = []
                for row in out["data"]:
                    cols = out.get("columns", [])
                    by_name = dict(zip(cols, row)) if cols else {}
                    projects.append(
                        cls(
                            id=by_name.get("ID") or 0,
                            slug=by_name.get("SLUG") or "",
                            name=by_name.get("NAME") or "",
                            description=by_name.get("DESCRIPTION"),
                            dashboard_ids=by_name.get("DASHBOARD_IDS"),
                            sort_order=int(by_name.get("SORT_ORDER") or 0),
                            is_active=by_name.get("IS_ACTIVE") or "Y",
                            created_at=by_name.get("CREATED_AT"),
                            updated_at=by_name.get("UPDATED_AT"),
                        )
                    )
                return projects
        except Exception:
            return []

    @classmethod
    def get_by_slug(cls, slug: str) -> Optional["ShellProject"]:
        """Проект по slug."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT ID, SLUG, NAME, DESCRIPTION, DASHBOARD_IDS, SORT_ORDER, IS_ACTIVE, CREATED_AT, UPDATED_AT
                    FROM UNA_SHELL_PROJECTS
                    WHERE UPPER(TRIM(SLUG)) = UPPER(TRIM(:slug))
                """
                out = db.execute_query(sql, {"slug": slug})
                if not out.get("success") or not out.get("data"):
                    return None
                row = out["data"][0]
                cols = out.get("columns", [])
                by_name = dict(zip(cols, row)) if cols else {}
                return cls(
                    id=by_name.get("ID") or 0,
                    slug=by_name.get("SLUG") or "",
                    name=by_name.get("NAME") or "",
                    description=by_name.get("DESCRIPTION"),
                    dashboard_ids=by_name.get("DASHBOARD_IDS"),
                    sort_order=int(by_name.get("SORT_ORDER") or 0),
                    is_active=by_name.get("IS_ACTIVE") or "Y",
                    created_at=by_name.get("CREATED_AT"),
                    updated_at=by_name.get("UPDATED_AT"),
                )
        except Exception:
            return None
