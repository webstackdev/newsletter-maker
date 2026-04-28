from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

# Unfold Admin Template
UNFOLD = {
    "SITE_TITLE": _("Newsletter Maker"),
    "SITE_HEADER": _("Newsletter Maker"),
    "SITE_SUBHEADER": _("Administration"),
    "SHOW_HISTORY": True,
    "DASHBOARD_CALLBACK": "core.utils.dashboard_callback",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/x-icon",
            "href": lambda request: static("core/favicon.ico"),
        },
    ],
    "SITE_ICON": lambda request: static("core/logo.png"),
    "SITE_SYMBOL": "speed",  # Material Icon for the sidebar
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "500": "168 85 247",
            "900": "88 28 135",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
    },
}

__all__ = ["UNFOLD"]
