# Coppel Scraper (Playwright)

Repositorio listo para GitHub Actions que usa Playwright (Chromium) para scrapear Coppel en dos modos:

- **PDP**: páginas de detalle de producto desde `urls.txt`.
- **PLP**: páginas de listado con paginación real a partir de `PLP_URL`.

El flujo usa un navegador real, reintentos con backoff, logs sin emojis, export a CSV/XLSX y envío de correo por SMTP. Siempre guarda artefactos en `outputs/`.

## Requisitos

- Python 3.12
- Playwright (Chromium)

## Uso local

1. Instala dependencias:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium --with-deps
```

2. Configura variables de entorno copiando `.env.example`:

```bash
cp .env.example .env
```

3. Ejecuta:

```bash
python -m src.run_scraper
```

## Modos de ejecución

### PDP (Product Detail Page)

- Define `MODE=pdp`.
- Edita `urls.txt` (una URL por línea).
- Opcional: `MAX_URLS` para limitar.

### PLP (Product Listing Page)

- Define `MODE=plp`.
- Define `PLP_URL=https://www.coppel.com/...`.
- `MAX_PAGES` controla la paginación.

## Outputs

Se generan en `outputs/`:

- `results.csv`
- `results.xlsx`
- `run.log`
- `summary.json`
- `debug/` (HTML y screenshots si hay fallos o si `DUMP_HTML=1`)

## Debug y bloqueo

Si detecta bloqueo (captcha o “Access Denied”), el scraper:

- marca el status como `BLOCK`
- guarda HTML y screenshot en `outputs/debug/`

Si `DUMP_HTML=1`, guarda HTML de cada página (PDP/PLP) para análisis posterior.

## Modo “parecer usuario” (stealth)

El scraper incluye heurísticas básicas para parecer navegación humana:

- `ENABLE_STEALTH=1`: desactiva `navigator.webdriver`, agrega idiomas y plugins simulados.
- `DISABLE_AUTOMATION_FLAGS=1`: deshabilita flags de automatización del navegador.
- `PERSISTENT_CONTEXT=1`: mantiene perfil/cookies en `PERSISTENT_CONTEXT_DIR`.
- `HEADLESS=0`: abre navegador visible (útil localmente; en GitHub Actions se recomienda `HEADLESS=1`).
- `BROWSER=chromium|firefox|webkit`: permite probar motores alternativos.
- `EXTRA_HEADERS_JSON`: headers extra en formato JSON (por ejemplo `{\"Referer\":\"https://www.coppel.com/\"}`).

## GitHub Actions

Workflow: `.github/workflows/coppel_cloud.yml`

Triggers:

- `workflow_dispatch`
- `schedule` (UTC)
- `push` a `main` solo si `RUN_ON_PUSH=1` (variable del repo)

Variables/Secrets recomendados:

- `MODE` (variable)
- `PLP_URL` (variable)
- `RUN_ON_PUSH` (variable: `1` o `0`)
- `EMAIL_SENDER` (secret)
- `EMAIL_PASSWORD` (secret)
- `EMAIL_TO` (secret)
- `EMAIL_SUBJECT` (secret, opcional)

## Troubleshooting

- **Bloqueo/captcha**: revisar `outputs/debug/`.
- **Timeouts**: aumenta `NAV_TIMEOUT_MS` y `WAIT_SELECTOR_MS`.
- **Falta de datos**: el DOM pudo cambiar; revisa HTML en debug.

## Alternativa C# (nota)

Si tu flujo futuro requiere C#, puedes considerar **HtmlAgilityPack** para parsear HTML. Este repositorio permanece en Python + Playwright, pero el enfoque de parseo se puede replicar con HtmlAgilityPack.
