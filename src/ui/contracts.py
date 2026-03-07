from dataclasses import dataclass
from typing import Any


class UiCommandId:
    OPEN = "open"
    OPEN_RECENT = "open_recent"
    SAVE = "save"
    CUT = "cut"
    COPY = "copy"
    PASTE = "paste"
    PASTE_PLAIN = "paste_plain"
    DELETE_SELECTION = "delete_selection"
    UNDO = "undo"
    REDO = "redo"
    DUPLICATE_SELECTION = "duplicate_selection"
    SORT_LINES_ASC = "sort_lines_asc"
    SORT_LINES_DESC = "sort_lines_desc"
    TRIM_TRAILING_SPACES = "trim_trailing_spaces"
    CHANGE_CASE_UPPER = "change_case_upper"
    CHANGE_CASE_LOWER = "change_case_lower"
    CHANGE_CASE_TITLE = "change_case_title"
    CHANGE_CASE_SENTENCE = "change_case_sentence"
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKE = "strike"
    ALIGN_LEFT = "align_left"
    ALIGN_CENTER = "align_center"
    ALIGN_RIGHT = "align_right"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    TEXT_COLOR = "text_color"
    HIGHLIGHT = "highlight"
    CLEAR_FORMATTING = "clear_formatting"
    LINE_SPACING = "line_spacing"
    FONT_FAMILY = "font_family"
    FONT_SIZE = "font_size"
    FONT_SIZE_INCREASE = "font_size_increase"
    FONT_SIZE_DECREASE = "font_size_decrease"
    APPLY_TEXT_STYLE = "apply_text_style"
    UPLOAD_FONT = "upload_font"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    ZOOM_SET = "zoom_set"
    INSERT_IMAGE = "insert_image"
    INSERT_HORIZONTAL_LINE = "insert_horizontal_line"
    INSERT_DATE_TIME = "insert_date_time"
    INSERT_SYMBOL = "insert_symbol"
    INSERT_TABLE = "insert_table"
    INSERT_CHECKLIST = "insert_checklist"
    INSERT_PAGE_BREAK = "insert_page_break"
    OPEN_MEMO_BUILDER = "open_memo_builder"
    NEW_FROM_TEMPLATE = "new_from_template"
    SAVE_AS_TEMPLATE = "save_as_template"
    FIND_REPLACE = "find_replace"
    DOCUMENT_SEARCH = "document_search"
    DOCUMENT_SEARCH_NEXT = "document_search_next"
    DOCUMENT_SEARCH_PREV = "document_search_prev"
    DOCUMENT_SEARCH_CLEAR = "document_search_clear"
    ACTION_HUB = "action_hub"
    EXPORT_TODO_REPORT = "export_todo_report"
    SHOW_STATS = "show_stats"
    SELECT_ALL = "select_all"
    EXPORT_PDF = "export_pdf"
    SPELL_CHECK = "spell_check"
    DICTIONARY_LOOKUP = "dictionary_lookup"
    WIKI_LOOKUP = "wiki_lookup"
    READ_ALOUD = "read_aloud"
    PICK_PAPER_COLOR = "pick_paper_color"
    TOGGLE_THEME = "toggle_theme"
    TOGGLE_FOCUS = "toggle_focus"
    TOGGLE_SIDEBAR = "toggle_sidebar"
    TOGGLE_CONSOLE = "toggle_console"
    TOGGLE_RULERS = "toggle_rulers"
    OPEN_COMMAND_PALETTE = "open_command_palette"
    SET_DEFAULT_LOGO = "set_default_logo"
    CLEAR_DEFAULT_LOGO = "clear_default_logo"
    NAVIGATE_TO_INDEX = "navigate_to_index"


@dataclass(frozen=True)
class UiCommandRequest:
    command_id: str
    payload: dict[str, Any] | None = None


@dataclass
class UiViewState:
    theme: str
    zoom: int
    dirty: bool
    sidebar_visible: bool
    focus_mode: bool
    show_console: bool
