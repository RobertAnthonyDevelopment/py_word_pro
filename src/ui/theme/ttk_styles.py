import tkinter as tk
from tkinter import ttk


def apply_ttk_styles(root: tk.Misc, colors: dict[str, str], density: str = "comfortable") -> None:
    style = ttk.Style(root)
    try:
        # `clam` gives us predictable cross-platform rendering for custom colors/depth.
        style.theme_use("clam")
    except Exception:
        pass

    pad_y = 12 if density == "comfortable" else 9
    pad_x = 18 if density == "comfortable" else 13

    style.configure(
        "App.TNotebook",
        background=colors["bg_panel"],
        borderwidth=3,
        relief="raised",
    )
    style.configure(
        "App.TNotebook.Tab",
        padding=(20, pad_y),
        background=colors["bg_surface_alt"],
        foreground=colors["text_secondary"],
        font=("Segoe UI", 11, "bold"),
        borderwidth=2,
        relief="raised",
    )
    style.map(
        "App.TNotebook.Tab",
        background=[("selected", colors["bg_surface"])],
        foreground=[("selected", colors["text_primary"])],
        relief=[("selected", "sunken")],
    )

    style.configure(
        "App.TCombobox",
        fieldbackground=colors["bg_surface"],
        foreground=colors["text_primary"],
        background=colors["bg_surface"],
        padding=(12, 8),
        bordercolor=colors["border_dark"],
        lightcolor=colors["border_light"],
        darkcolor=colors["border_dark"],
        arrowsize=18,
        relief="groove",
    )

    style.configure(
        "Nav.Treeview",
        background=colors["bg_surface"],
        fieldbackground=colors["bg_surface"],
        foreground=colors["text_primary"],
        bordercolor=colors["border"],
        borderwidth=0,
        rowheight=36,
        font=("Segoe UI", 11),
    )
    style.configure(
        "Nav.Treeview.Heading",
        font=("Segoe UI", 10, "bold"),
        padding=(8, 6),
        relief="raised",
    )
    style.map(
        "Nav.Treeview",
        background=[("selected", colors["accent"])],
        foreground=[("selected", "#FFFFFF")],
    )

    style.configure(
        "App.TSeparator",
        background=colors["border"],
    )

    # Keep global option spacing aligned with styled controls.
    try:
        root.option_add("*TCombobox*Listbox*selectBackground", colors["accent"])
        root.option_add("*TCombobox*Listbox*selectForeground", "#FFFFFF")
        root.option_add("*Button.padX", pad_x)
        root.option_add("*Button.padY", max(4, pad_y // 2))
        # Keep family names with spaces valid for Tk option parsing.
        root.option_add("*Button.font", ("Segoe UI", 11, "bold"))
    except Exception:
        pass
