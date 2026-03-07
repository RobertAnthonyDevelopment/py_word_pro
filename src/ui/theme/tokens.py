LIGHT_TOKENS = {
    "bg_app": "#EAF1FB",
    "bg_surface": "#FFFFFF",
    "bg_surface_alt": "#E4EDFF",
    "bg_panel": "#EDF3FF",
    "border": "#BACAE2",
    "border_dark": "#8FA7CA",
    "border_light": "#FFFFFF",
    "text_primary": "#152033",
    "text_secondary": "#3D4F68",
    "accent": "#2A63F6",
    "accent_hover": "#1E4FD0",
    "danger": "#C23838",
    # Compatibility aliases for existing logic/widget modules.
    "ribbon": "#ECF3FF",
    "bg": "#EAF1FB",
    "paper": "#FFFFFF",
    "text": "#152033",
    "ruler": "#DDE7F5",
    "sidebar": "#ECF3FF",
    "primary": "#2A63F6",
    "console": "#E4ECFA",
}


DARK_TOKENS = {
    "bg_app": "#141A27",
    "bg_surface": "#252F45",
    "bg_surface_alt": "#2F3D59",
    "bg_panel": "#1C2740",
    "border": "#3A4B6C",
    "border_dark": "#2B3955",
    "border_light": "#5F7396",
    "text_primary": "#E9EEF8",
    "text_secondary": "#A8B6CC",
    "accent": "#5B86FF",
    "accent_hover": "#4771E4",
    "danger": "#E06A6A",
    # Compatibility aliases for existing logic/widget modules.
    "ribbon": "#1A2336",
    "bg": "#141A27",
    "paper": "#1E273A",
    "text": "#E9EEF8",
    "ruler": "#233147",
    "sidebar": "#1A2336",
    "primary": "#5B86FF",
    "console": "#101726",
}


def get_theme_tokens(theme_name: str) -> dict[str, str]:
    if theme_name == "dark":
        return dict(DARK_TOKENS)
    return dict(LIGHT_TOKENS)
