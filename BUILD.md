# TutorMap Build Guide

## Local Build

Run the static site generator from the project root.

```bash
python build.py
```

The build creates the `output/` directory. Generated files are build artifacts and are not source files.

If `output/content_generation_report.xlsx` is open in Excel, the build writes a temporary report and continues. Close Excel before building when you need the main report file replaced.

## Vercel Deployment

Vercel should use the project build command and output directory.

```text
Build Command: python3 build.py
Output Directory: output
```

The `output/` directory is generated during the Vercel build. It should not be committed as source.

## Cache Check

Each generated HTML page includes build metadata at the bottom.

```html
<!--
Build Time: ...
Build Version: ...
Template: ...
-->
```

When checking a deployment, compare the `Build Version` in the live HTML with the latest Vercel build log.

## Production HTML Check

Fetch the homepage HTML and confirm the current build is being served.

```bash
curl -L https://tutormap.co.kr/
```

Confirm the homepage subject cards render as links.

```html
<a class="card link-card" href="...">
```

The homepage subject shortcut area should not contain `muted-card`.

## Hard Refresh

When browser cache may be stale, use a hard refresh.

```text
Windows Chrome/Edge: Ctrl + F5
macOS Chrome/Edge: Command + Shift + R
Safari: Option + Command + E, then reload
```

For deployment cache checks, prefer fetching the HTML directly instead of relying only on the browser view.
