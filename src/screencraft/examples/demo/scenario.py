"""Demo scenario: the bundled Notely app (examples/demo-app). ~16 s of footage.

Run via `screencraft demo`, or by hand:
    python3 -m http.server 8765 --directory examples/demo-app
    screencraft record examples/demo/scenario.py --out out/demo/footage --base-url http://127.0.0.1:8765
"""

CONFIG = {
    "base_url": "http://127.0.0.1:8765",   # overridden by `screencraft demo`
    "start_path": "/",
    "scale": 2,
    "viewport": {"width": 1920, "height": 1080},
    "locale": "en-US",
    "cursor_start": [1150, 700],
}

TEXT = "Planned the launch with the team. Idea: a weekly digest email. Follow up with Anna about the schedule."


def run(take, page):
    take.mark("hook")
    take.hold(0.8)

    # 1. focus the composer, park the pointer, type one paragraph
    tb = take.click("#entry", dur=0.7, name="entry")
    take.hold(0.25)
    take.move(tb["x"] + tb["width"] * 0.82, tb["y"] + tb["height"] + 90, 0.45)
    take.hold(0.15)
    take.mark("type_start")
    take.type(TEXT, cps=34)
    take.mark("type_end")
    take.hold(0.5)

    # 2. turn it into notes
    take.click("#make", dur=0.6, name="make")
    take.mark("make")
    page.wait_for_selector("#note-3.in", timeout=10000)
    take.hold(0.3)
    take.mark("notes")
    take.box("notes", "#notes")
    nb = take.box("note1", "#note-1")
    take.move(nb["x"] + nb["width"] * 0.3, nb["y"] + nb["height"] * 0.6, 0.8)
    take.hold(0.7)

    # 3. pin the first note (custom tooltip shows on hover)
    take.click("#note-1 .pin", dur=0.6, name="pin")
    take.mark("pin")
    take.hold(1.4)

    # 4. scroll to the archive, hover a row
    take.mark("scroll")
    row = take.scroll_into_view("#item-6", offset=420, dur=1.4)
    take.box_at("item6", row)
    take.move(row["x"] + row["width"] * 0.3, row["y"] + row["height"] / 2, 0.7)
    take.mark("hover")
    take.hold(1.6)
    take.mark("end")
