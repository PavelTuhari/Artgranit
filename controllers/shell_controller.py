"""
Контроллер Shell: основной список проектов, каждый проект — свой префикс и набор дашбордов.
MVP + OOP.
"""
from typing import Dict, Any, List, Optional
from models.shell_project import ShellProject


# Префикс URL shell (una.md/shell)
SHELL_URL_PREFIX = "/una.md/shell"


class ShellController:
    """Управление shell-проектами и маршрутами."""

    @staticmethod
    def get_all_projects(active_only: bool = True) -> List[Dict[str, Any]]:
        """Список всех проектов для страницы /una.md/shell/projects."""
        projects = ShellProject.get_all(active_only=active_only)
        return [p.to_dict() for p in projects]

    @staticmethod
    def get_project_by_slug(slug: str) -> Optional[Dict[str, Any]]:
        """Проект по slug (для открытия /una.md/shell/<slug>)."""
        project = ShellProject.get_by_slug(slug)
        return project.to_dict() if project else None

    @staticmethod
    def project_links(base_url: str = "") -> List[Dict[str, Any]]:
        """Список ссылок на проекты: { name, slug, url, description }.
        base_url — например request.host_url или '' для относительных путей.
        В конец добавляется ссылка на приложение «Агенты» (Nuxt SPA под тем же портом)."""
        projects = ShellProject.get_all(active_only=True)
        prefix = base_url.rstrip("/") + SHELL_URL_PREFIX if base_url else SHELL_URL_PREFIX
        links = [
            {
                "name": p.name,
                "slug": p.slug,
                "url": f"{prefix}/{p.slug}",
                "description": p.description or "",
            }
            for p in projects
        ]
        # Приложение «Агенты» (Nuxt SPA) — тот же хост/порт, подлинк /una.md/shell/agents
        links.append({
            "name": "Агенты (бухгалтерия, страховки)",
            "slug": "agents",
            "url": f"{prefix}/agents",
            "description": "Симуляция агента-бухгалтера QuickBooks/TaxAct и агентов по страховкам.",
        })
        return links
