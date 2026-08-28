from PIL import Image, ImageDraw, ImageFont

# Create a clean white food packaging label (600x500 px)
img = Image.new("RGB", (600, 500), color="#FFFFFF")
draw = ImageDraw.Draw(img)

# Product lines
lines = [
    ("ORGANIC ROASTED ALMONDS", 25),
    ("--------------------------------------------------", 55),
    ("Net Quantity: 250 g", 85),
    ("MRP: Rs. 199.00 (Incl. of all taxes)", 125),
    ("Unit Sale Price (USP): Rs. 0.80 / g", 165),
    ("Date of Pkg: 03/2026", 205),
    ("Manufactured by: Pramand Foods Pvt Ltd, Pune 411001", 245),
    ("Consumer Care: support@pramand.com, Toll Free: 1800-222-3333", 285),
    ("Country of Origin: India", 325),
]

# Draw text onto image
for text, y in lines:
    draw.text((30, y), text, fill="#111111")

# Draw a bounding border around the packaging label
draw.rectangle([(10, 10), (590, 490)], outline="#2D6A4F", width=3)

# Save to disk
img.save("test_label_food.png")
print("Saved sample packaging label as 'test_label_food.png'")