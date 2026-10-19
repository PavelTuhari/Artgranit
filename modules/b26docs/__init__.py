"""Vizualizatorul documentatiei proiectului Biro26.

RO: pina acum documentele .md ale modulului nu se puteau deschide din portal —
existau doar in repository, iar hub-ul arata o pagina HTML statica. Legaturile
«unde e documentat asta?» duceau in gol. Modulul le randeaza in browser:
markdown -> HTML, cu indexul tuturor documentelor si cautare.

Citeste DOAR din docs/<folder>/, doar fisiere .md/.html si doar din lista
albila de foldere — un vizualizator de fisiere care accepta orice cale ar fi
o gaura de securitate (path traversal).

EN: renders the project's markdown docs in the portal; read-only, allow-listed
folders, no path traversal.
"""
from flask import Blueprint

blueprint = Blueprint(
    "b26docs",
    __name__,
    template_folder="templates",
)

from modules.b26docs import routes  # noqa: E402,F401  (înregistrează rutele)

__all__ = ["blueprint"]
