import os

fonts_dir = r"C:\Windows\Fonts"
fonts = [f for f in os.listdir(fonts_dir) if f.lower().endswith(".ttf")]

for f in fonts:
    print(f)
