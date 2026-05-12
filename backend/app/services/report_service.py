
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from pathlib import Path

def generate_flood_report(prediction_id: str, meta: dict, output_path: str):
    """
    Generate a simple PDF report using Pillow (Safe Version).
    """
    width, height = 800, 1100
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Simple Title Box
    draw.rectangle([0, 0, width, 100], fill=(13, 17, 23))
    
    y = 130
    draw.text((30, y), f"SENTINEL-AI INTELLIGENCE REPORT", fill=(0, 0, 0))
    y += 30
    draw.text((30, y), f"Report ID: {prediction_id}", fill=(0, 0, 0))
    y += 30
    draw.text((30, y), f"Date: {datetime.now().strftime('%Y-%m-%d')}", fill=(0, 0, 0))
    
    y += 50
    stats = meta.get("stats", {})
    f_pct = stats.get("flooded_percentage", 0)
    
    draw.text((30, y), f"FLOODED PERCENTAGE: {f_pct}%", fill=(0, 0, 0))
    y += 40
    
    # Progress bar as risk indicator
    draw.rectangle([30, y, 770, y+30], outline=(200, 200, 200))
    bar_color = (220, 53, 69) if f_pct > 30 else (255, 193, 7) if f_pct > 10 else (40, 167, 69)
    draw.rectangle([30, y, 30 + (f_pct * 7.4), y+30], fill=bar_color)
    
    y += 100
    draw.text((30, y), "LOCATIONS IDENTIFIED:", fill=(0, 0, 0))
    y += 30
    for loc in meta.get("locations_flooded", []):
        draw.text((50, y), f"- {loc}", fill=(50, 50, 50))
        y += 25
        
    img.save(output_path, "PDF")
    return output_path
