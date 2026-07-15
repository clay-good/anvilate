# VHS tape for the README hero GIF.
# Render with: vhs docs/demo.tape   (needs vhs + ttyd + ffmpeg)
Output docs/demo.gif

Set Shell bash
Set FontSize 17
Set Width 1120
Set Height 660
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "source .venv/bin/activate; export PS1='$ '; clear"
Enter
Show

Sleep 700ms
Type "# Describe a part's loads, get a physics-validated pass/fail — every check cites its code."
Enter
Sleep 1200ms

Type "python examples/cantilever_bracket_check.py"
Enter
Sleep 2600ms

Type "# Passes strength, but the deflection screen fails. No silent green."
Enter
Sleep 1800ms

Type "python examples/lug_drawing.py"
Enter
Sleep 2600ms

Type "# Checks pass (ASME BTH-1) -> a fabrication-ready DXF drops out the end."
Enter
Sleep 1600ms

Type "ls padeye.dxf"
Enter
Sleep 2600ms
