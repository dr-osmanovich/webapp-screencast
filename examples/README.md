# Examples

The runnable demo ships inside the package so `webapp-screencast demo` works after `pip install`:

- [`src/webapp_screencast/examples/demo-app/`](../src/webapp_screencast/examples/demo-app/) — Notely, a single-page app with a composer, cards, a pin with a CSS tooltip and a long archive to scroll.
- [`src/webapp_screencast/examples/demo/scenario.py`](../src/webapp_screencast/examples/demo/scenario.py) — the storyboard as `take.*` actions with marks and boxes.
- [`src/webapp_screencast/examples/demo/plan.py`](../src/webapp_screencast/examples/demo/plan.py) — camera, subtitles, cards, callout, halo.

Copy the two Python files next to your own project, point `CONFIG["base_url"]` at your app and edit from there.
