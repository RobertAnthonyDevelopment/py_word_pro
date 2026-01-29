# PyWord Pro

**PyWord Pro** is a modern, lightweight, and professional document editor built with Python and Tkinter. It features a clean, modular architecture designed for extensibility and rich text editing capabilities.

<img width="1603" height="931" alt="py_word_pro" src="https://github.com/user-attachments/assets/b9a33eb0-9098-42de-b94f-195c51aa5d2a" />

## Features

* **Professional Document Editing:** Rich text support with fonts, sizes, colors, and alignment.
* **Modular Architecture:** Cleanly separated UI, Logic, and Configuration for scalability.
* **File Support:** Open and Save `.docx`,`.pdf`, `.txt`, `.md`, and `.py`.
* **Export Options:** Export documents to professionally formatted PDF or Markdown.
* **Media Support:** Insert images and resize them dynamically.
* **Theming:** Built-in Light and Dark modes.

## Installation

### Prerequisites
* Python 3.10 or higher
* pip (Python Package Manager)

### Setup
1.  Clone the repository:
    ```bash
    git clone https://github.com/RobertAnthonyDevelopment/py_word_pro.git
    cd py_word_pro
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

To start the application, run the main entry point from your terminal:

```bash
python main.py

PyWordPro/
├── main.py                 # Application Entry Point
├── requirements.txt        # Dependencies
├── src/
│   ├── config.py           # Global Settings & Themes
│   ├── app.py              # Main Application Controller
│   ├── ui/                 # User Interface Modules
│   │   ├── ribbon.py       # Top Menu Bar
│   │   ├── sidebar.py      # Navigation Panel
│   │   ├── workspace.py    # Editor & Rulers
│   │   └── ...
│   └── logic/              # Backend Logic Modules
│       ├── file_manager.py # I/O Operations
│       ├── syntax.py       # Syntax Highlighting Engine
│       └── developer.py    # Threaded Code Execution

```

## Contributing

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

## License

Distributed under the MIT License. 

---

**Developed by Robert Anthony Development**
