from typing import Any, Dict, List

from app.schemas import UIReport, UIScreen, UIStyles

REQUIRED_SCREENS = [
    "Home Screen",
    "Login Screen",
    "Product Page",
    "Category Page",
    "Cart Page",
    "Checkout Page",
]

DEFAULT_STYLE = {
    "colors": {
        "primary": "#0055FF",
        "secondary": "#FFFFFF",
        "accent": "#111111",
    },
    "typography": {
        "font": "Inter",
        "weight_scale": {
            "heading": "700",
            "body": "400",
            "caption": "300",
        },
    },
    "components": ["Header", "Button", "ProductCard"],
}


def generate_ui_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backwards-compatible helper left for importers.
    """
    report = build_ui_report_from_payload(data, "")
    return report.model_dump()


def build_ui_report_from_payload(payload: Dict[str, Any], document_text: str) -> UIReport:
    project_name = payload.get("project_name") or "Auto-Generated E-Commerce Experience"

    summary = payload.get("summary")
    if not summary:
        summary = (document_text[:400] + "...") if len(document_text) > 400 else document_text

    screens = _normalize_screens(payload.get("screens", []))
    styles = _normalize_styles(payload.get("styles", {}))

    return UIReport(
        project_name=project_name,
        screens=screens,
        styles=styles,
        summary=summary or "Automated UI/UX report generated from source document.",
    )


def _normalize_screens(screens_payload: List[Dict[str, Any]]) -> List[UIScreen]:
    screens_by_name: Dict[str, UIScreen] = {}

    for screen in screens_payload:
        name = (screen or {}).get("name")
        if not name:
            continue

        layout = screen.get("layout") or {}
        description = screen.get("description") or "Auto generated description."

        screens_by_name[name.lower()] = UIScreen(
            name=name,
            layout=layout,
            description=description
        )

    # Add default screens if missing
    for required in REQUIRED_SCREENS:
        key = required.lower()
        if key not in screens_by_name:
            screens_by_name[key] = UIScreen(
                name=required,
                layout={"placeholder": "Awaiting details from document"},
                description=f"Default layout for {required}.",
            )

    return list(screens_by_name.values())


def _normalize_styles(styles_payload: Dict[str, Any]) -> UIStyles:
    colors = styles_payload.get("colors") or DEFAULT_STYLE["colors"]
    typography = styles_payload.get("typography") or DEFAULT_STYLE["typography"]
    components = styles_payload.get("components") or DEFAULT_STYLE["components"]

    return UIStyles(
        colors=colors,
        typography=typography,
        components=components
    )
