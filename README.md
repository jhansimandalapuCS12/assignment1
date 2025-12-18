# UI/UX Auto-Design Generator

Upload an e-commerce PDF/DOCX brief, let Groq/Gemini analyze the content, duplicate a live Figma file, and instantly draw production-ready screens through a Figma plugin.

## Highlights
- **FastAPI backend** (`app/main.py`) orchestrates upload, parsing, LLM analysis, UI normalization, and Figma duplication.
- **PyPDF2 + python-docx** extraction pipeline with graceful fallbacks.
- **Groq _or_ Gemini** (configurable) output structured `UIReport` JSON.
- **Figma REST + Plugin**: REST duplicates a template file; the companion plugin renders real frames/pages using the JSON blueprint.
- **End-to-end automation**: Home/Login/Product/Category/Cart/Checkout screens are always present, plus any custom screens detected by the LLM.

## Project Structure
```
Assignment/
├── app/
│   ├── main.py                # FastAPI router + orchestration
│   ├── schemas.py             # Pydantic models
│   └── services/
│       ├── figma_client.py    # REST helper + fallback link creation
│       ├── llm.py             # Groq/Gemini abstraction
│       ├── parser.py          # PDF/DOCX extraction helpers
│       └── ui_generator.py    # Normalizes LLM output into UIReport
├── figma-plugin/
│   ├── manifest.json
│   ├── code.js                # Figma plugin controller
│   └── ui.html                # Plugin UI (upload + JSON renderer)
├── public/                    # (reserved for future web UI)
├── requirements.txt
└── README.md
```

## Prerequisites
- Python 3.11+
- Node 18+ (for plugin bundling if you customize assets)
- Figma desktop or web editor with **Developer Mode**
- Accounts + API keys:
  - [Groq](https://console.groq.com/) and/or [Google AI Studio](https://ai.google.dev/)
  - [Figma personal access token](https://www.figma.com/developers/api#access-tokens)

## Environment Variables
Create `.env` with the following (unset values fall back to safe defaults but real automation requires them):

```env
# LLM
LLM_PROVIDER=groq                  # groq | gemini
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama3-70b-versatile
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-1.5-flash

# Figma
FIGMA_ACCESS_TOKEN=pat_xxx
FIGMA_TEMPLATE_FILE_KEY=AbCdEf12GhIj
FIGMA_PROJECT_ID=123456789012345678   # Numeric project inside your team

# Misc
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
SAMPLE_DOCUMENT_PATH=./sample-data/ecommerce_uiux_report.pdf
```

> **Note:** Figma’s REST API cannot create nodes; we duplicate a template file via `/files/{key}/duplicate`. Open the duplicated file, run the plugin, and it will draw the UI.

## Install & Run
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Server will expose:
- `POST /upload` – main entry point used by the plugin UI  
- `POST /sample-report` – helper that replays `SAMPLE_DOCUMENT_PATH`  
- `GET /health` – returns provider + Figma readiness info

### Testing with the Sample Document
1. Place your document at `sample-data/ecommerce_uiux_report.pdf` (copy it from `@/mnt/data/ecommerce_uiux_report.pdf` if available).
2. Hit:
   ```bash
   curl -X POST http://localhost:8000/sample-report
   ```
3. Response contains `figma_url` (duplicated file or fallback link) and `report`.

## FastAPI Endpoint Contract
`POST /upload`
- **Body**: `multipart/form-data` with `file` (PDF/DOCX)
- **Response**:
```json
{
  "figma_url": "https://www.figma.com/file/<new-file>",
  "report": {
    "project_name": "Modern E-commerce App",
    "summary": "Vibrant mobile-first design with gradient components",
    "screens": [
      {
        "name": "Home Screen",
        "layout": {
          "sections": [
            {
              "component": "gradient_banner",
              "gradient": "linear #FF6B6B → #4ECDC4",
              "height": 280,
              "title_style": "Poppins 800 42px white",
              "padding": 40
            },
            {
              "component": "filter_chips",
              "chip_style": {
                "background": "rgba(255,255,255,0.15)",
                "border_radius": 25,
                "box_shadow": "0 4px 15px rgba(0,0,0,0.1)"
              },
              "items": ["Electronics", "Fashion", "Home"]
            },
            {
              "component": "event_cards",
              "card_style": {
                "background": "white",
                "border_radius": 24,
                "box_shadow": "0 8px 32px rgba(0,0,0,0.12)"
              },
              "grid_columns": 2
            }
          ]
        },
        "description": "Modern home screen with gradient banner and product cards"
      }
    ],
    "styles": {
      "colors": {
        "primary": "#FF6B6B",
        "secondary": "#4ECDC4",
        "accent": "#FFE66D"
      },
      "typography": {
        "display": "Poppins 800",
        "heading": "Poppins 700",
        "body": "Inter 500"
      },
      "components": [
        "gradient_banner",
        "filter_chips",
        "event_cards",
        "elevated_container",
        "floating_action_button"
      ]
    }
  }
}
```

## Figma Plugin Usage
1. In Figma, go to `Plugins → Development → Import plugin from manifest…` and select `figma-plugin/manifest.json`.
2. Open the freshly duplicated file URL (from the backend response) or any sandbox file.
3. Run **Auto UI/UX Screen Builder**:
   - Option A: Upload the same PDF/DOCX straight from the plugin UI (it calls the FastAPI `/upload` endpoint).
   - Option B: Paste the `report` JSON returned by the backend.
4. Click **Render In Figma**. The plugin will:
   - Create a new page named after the project.
   - Draw frames for every screen, respecting layouts/colors.
   - Build section cards describing each layout block.
5. The plugin reports status back to the UI and shows the latest `figma_url`.

## Implementation Notes
- **Text extraction** lives in `app/services/parser.py` using PyPDF2 + python-docx, with fallbacks to UTF-8 decoding.
- **LLM adapter** (`app/services/llm.py`) enforces JSON-only replies and rescues malformed JSON snippets.
- **UI normalization** ensures mandatory screens exist even if the document omits them.
- **Figma REST** (`app/services/figma_client.py`) gracefully falls back to a fake link when tokens are missing, so local dev still works.
- **Plugin rendering** (`figma-plugin/code.js`) loads Inter/Roboto fonts, lays out frames in a grid, and prints each layout entry inside stylized cards.

## Future Enhancements
- Persist uploaded reports with job IDs for later retrieval.
- Map layout sections to real auto-layout components (buttons, cards, etc.).
- Add authentication + rate limiting before exposing the API publicly.

---
Made with FastAPI + Groq/Gemini + Figma Plugins API. Upload, analyze, and draw—automatically.
