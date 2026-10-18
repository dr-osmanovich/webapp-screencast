"""Demo plan: camera, subtitles, cards and annotations for examples/demo/scenario.py.

All times are footage seconds (from marks); `screencraft compose` converts them.
"""


def plan(ctx):
    m = ctx.m
    return {
        "title": "Notely — type once, notes appear",
        "lang": "en",
        "tag": "Made with screencraft",
        "intro": {"title": "Type once. <b>Notes</b> appear.", "subtitle": "Notely · demo app", "duration": 1.6},
        "outro": {"title": "Notely", "line": "Your day, in cards.", "duration": 3.2, "overlap": 0.45,
                  "subtitle": "Notely: your day, in cards."},
        "look": {"wallpaper": "violet", "accent": "#5444E6"},
        "camera": [
            {"from": -99, "zoom": 1.0, "focus": "center"},
            {"from": m("type_start") - 0.8, "zoom": 1.6, "focus": ctx.center("entry", 0, 60)},
            {"from": m("type_end") + 0.25, "zoom": 1.55, "focus": "cursor"},
            {"from": m("make") + 0.45, "zoom": 1.45, "focus": ctx.center("notes", 0, 0)},
            {"from": m("pin") - 0.9, "zoom": 1.7, "focus": "cursor"},
            {"from": m("pin") + 1.0, "zoom": 1.0, "focus": "center"},
            {"from": m("scroll_end") + 0.1, "zoom": 1.5, "focus": ctx.center("item6", 0, 40)},
        ],
        "subtitles": [
            [m("type_start") - 0.3, m("type_end") + 0.2, "Write the day as one paragraph."],
            [m("make") - 0.1, m("pin") - 0.6, "One click turns it into tidy cards."],
            [m("pin") - 0.5, m("pin") + 1.3, "Pin what matters."],
            [m("scroll") + 0.2, m("hover") + 1.4, "Everything earlier stays one scroll away."],
        ],
        "callouts": [
            {"at": m("pin") + 0.35, "until": m("scroll"), "html": "Pinned notes <b>stay on top</b>",
             "x": ctx.box("pin")["x"] - 300, "y": ctx.box("pin")["y"] + ctx.box("pin")["h"] + 16, "side": "below"},
        ],
        "halos": [{"at": m("pin") + 0.15, "box": "pin"}],
    }
