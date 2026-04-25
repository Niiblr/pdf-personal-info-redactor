# 📄 PDF Personal Info Redactor

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A command-line tool that **automatically redacts personal information from PDF documents**, using exact string matching and/or AI-powered detection via a local LLM. No data leaves your machine; everything runs locally.

---

## ✨ Features

- **Exact Match Redaction:** Provide a list of strings (names, addresses, etc.) and the tool finds and redacts every occurrence across all pages
- **AI Header Scan:** Uses a local LLM (via [Ollama](https://ollama.com)) to intelligently identify PII in document headers you may have missed
- **Batch Processing:** Drop multiple PDFs into the `input/` folder and redact them all in one run
- **Fully Local:** No cloud APIs, no data leaves your machine
- **Dual Mode:** Use exact match, AI scan, or both together in a single pass

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Niiblr/pdf-personal-info-redactor.git
cd pdf-personal-info-redactor
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your PDFs

Place the PDF files you want to redact into the `input/` folder:

```bash
mkdir input output
cp /path/to/your/documents/*.pdf input/
```

### 4. Configure your PII strings

Copy the example file and add your personal information:

```bash
cp pii.txt.example pii.txt
```

Edit `pii.txt` with the strings you want to redact, one per line:

```text
# Lines starting with # are ignored
Jane Doe
J. Doe
456 Oak Avenue
Springfield
IL 62704
jane.doe@email.com
```

### 5. Run the redactor

```bash
python redact.py
```

Redacted PDFs will appear in the `output/` folder.

---

## 📖 Usage

### Exact match only (default)

```bash
# Reads strings from pii.txt automatically
python redact.py

# Pass strings directly on the command line
python redact.py --pii "Jane Doe" "456 Oak Avenue" "IL 62704"
```

### AI scan only

```bash
python redact.py --ai --no-pii-file
```

### Both modes together (recommended)

```bash
# AI scan on top of pii.txt strings
python redact.py --ai

# CLI strings + AI scan
python redact.py --pii "Jane Doe" --ai
```

### Additional options

```bash
# Use a different model
python redact.py --ai --model llama3.2

# Scan more of the page (default: top 30%)
python redact.py --ai --fraction 0.45

# Custom input/output directories
python redact.py --input ./my_docs --output ./redacted
```

---

## 🤖 Using with a Local Model (Ollama)

The AI detection mode uses [Ollama](https://ollama.com) to run a language model **entirely on your machine**: no API keys, no cloud, no data leaving your computer.

### Step 1: Install Ollama

Download and install from [ollama.com](https://ollama.com):

| Platform | Install |
|----------|---------|
| **Windows** | Download the installer from [ollama.com/download](https://ollama.com/download) |
| **macOS** | `brew install ollama` or download from [ollama.com/download](https://ollama.com/download) |
| **Linux** | `curl -fsSL https://ollama.com/install.sh \| sh` |

### Step 2: Pull a model

```bash
ollama pull llama3.2
```

### Step 3: Verify Ollama is running

```bash
ollama list
```

You should see your model listed. If Ollama isn't running, start it with:

```bash
ollama serve
```

### Step 4: Run with AI mode

```bash
python redact.py --ai --model llama3.2
```

### Recommended models

| Model | Size | Speed | Quality | Command |
|-------|------|-------|---------|---------|
| **qwen2.5:32b** | ~19 GB | 🐢 Slow | ★★★★★ | `ollama pull qwen2.5:32b` |
| **gpt-oss:20b** | ~12 GB | 🐢 Slow | ★★★★★ | `ollama pull gpt-oss:20b` |
| **llama3.2** | ~2 GB | ⚡ Fast | ★★★★☆ | `ollama pull llama3.2` |
| **gemma3** | ~5 GB | ⚡ Fast | ★★★★☆ | `ollama pull gemma3` |
| **mistral** | ~4 GB | ⚡ Fast | ★★★★☆ | `ollama pull mistral` |
| **glm-4.7-flash** | ~5 GB | ⚡ Fast | ★★★★☆ | `ollama pull glm-4.7-flash` |

> **💡 Tip:** `llama3.2` is the recommended default: small, fast, and accurate enough for PII detection. Any model that can follow JSON output instructions will work.

---

## ⚙️ Configuration

### `pii.txt` format

```text
# Comments start with #
# One string per line, case-sensitive

Full Name
Street Address Line 1
City
Postcode
email@example.com
```

**Tips:**
- Split multi-line addresses into separate lines (one per line)
- Include common variations (e.g., `John Smith` and `J. Smith`)
- Matching is case-sensitive, so use the exact casing from your PDFs

### CLI reference

| Flag | Description | Default |
|------|-------------|---------|
| `--pii STRING [STRING ...]` | Strings to redact (exact match) | none |
| `--ai` | Enable AI header scan on page 1 | off |
| `--no-pii-file` | Ignore `pii.txt` even if it exists | off |
| `--model MODEL` | Ollama model name | `llama3.2` |
| `--fraction N` | Page fraction for AI scan (0.0–1.0) | `0.30` |
| `--input DIR` | Input directory | `./input` |
| `--output DIR` | Output directory | `./output` |

---

## 🔧 How It Works

```
input/*.pdf
    │
    ├──► Mode 1: Exact Match
    │    Search every page for each string in pii.txt / --pii args
    │    Draw white redaction boxes over every match
    │
    ├──► Mode 2: AI Header Scan (optional)
    │    Extract text blocks from top N% of page 1
    │    Send to local LLM → "which blocks contain PII?"
    │    Redact the flagged blocks
    │
    └──► Save redacted PDF to output/
```

1. **Exact match** uses PyMuPDF's `search_for()` to locate text rectangles and applies redaction annotations with a white fill
2. **AI scan** extracts text blocks from the header region, sends them to Ollama with a structured prompt, and parses the JSON response to identify PII indices
3. Both modes can run in a single pass: exact match runs first, then AI catches anything you missed

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## 📄 License

This project is licensed under the [MIT License](LICENSE). Do whatever you want with it.
