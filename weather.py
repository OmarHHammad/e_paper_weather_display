import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import requests

# Automatically add the 'lib' directory
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, 'lib')
sys.path.append(lib_path)
from waveshare_epd import epd7in5_V2

# User defined configuration
API_KEY = 'XXXXXXXX'  # Your API key
LOCATION = 'Seattle, Washington'  # Name of location
LATITUDE = 'XXXXXXXX'  # Latitude
LONGITUDE = 'XXXXXXXX'  # Longitude
UNITS = 'imperial'  # imperial or metric

BASE_URL = f'https://api.openweathermap.org/data/3.0/onecall'
FONT_DIR = os.path.join(os.path.dirname(__file__), 'font')
PIC_DIR = os.path.join(os.path.dirname(__file__), 'pic')
ICON_DIR = os.path.join(PIC_DIR, 'icon')

# Initialize display
epd = epd7in5_V2.EPD()
epd.init()
epd.Clear()

# Logging configuration
LOG_FILE = 'weather_display.log'
logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(console_handler)
logger.info("Weather display script started.")

# Font definitions
font18 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 18)
font22 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 22)
font24 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 24)
font30 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 30)
font40 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 40)  # For High/Low
font50 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 50)
font100 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 100)
font160 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 160)
font_small = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 24)
font_tiny = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 14)
font_location = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 20)

COLORS = {'black': 'rgb(0,0,0)', 'white': 'rgb(255,255,255)', 'grey': 'rgb(235,235,235)'}

# Fetch weather data
def fetch_weather_data():
    url = f"{BASE_URL}?lat={LATITUDE}&lon={LONGITUDE}&units={UNITS}&appid={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch weather data: {e}")
        raise

def process_weather_data(data):
    try:
        current = data['current']
        daily = data['daily']
        minutely = data.get('minutely', [])

        weather_data = {
            "temp_current": current['temp'],
            "report": current['weather'][0]['description'].title(),
            "icon_code": current['weather'][0]['icon'],
            "temp_max": daily[0]['temp']['max'],
            "temp_min": daily[0]['temp']['min'],
            "precip_percent": daily[0]['pop'] * 100,
            "minutely_precipitation": [minute['precipitation'] for minute in minutely] if minutely else [],
            "daily_forecast": [],
            "sunrise": current['sunrise'],
            "sunset": current['sunset'],
            "uvi": current['uvi'],
        }
        for day_data in daily[:5]:
            forecast_entry = {
                "date": datetime.fromtimestamp(day_data['dt']).strftime('%a'),
                "temp_max": day_data['temp']['max'],
                "temp_min": day_data['temp']['min'],
                "icon_code": day_data['weather'][0]['icon'],
                "description": day_data['weather'][0]['description'].title()
            }
            weather_data["daily_forecast"].append(forecast_entry)
        return weather_data
    except KeyError as e:
        logging.error(f"Error processing weather data: {e}")
        raise

# Generate display image
def generate_display_image(weather_data):
    try:
        # Create a new blank image
        template = Image.new('1', (epd.width, epd.height), 255)
        draw = ImageDraw.Draw(template)

        # --- Section Dividers ---
        draw.line([(0, 190), (epd.width, 190)], fill=COLORS['black'], width=2)
        draw.line([(330, 190), (330, epd.height)], fill=COLORS['black'], width=2)


        icon_path = os.path.join(ICON_DIR, f"{weather_data['icon_code']}.png")
        icon_image = Image.open(icon_path) if os.path.exists(icon_path) else None

        if icon_image:
            template.paste(icon_image, (40, 15))  # Original icon position

        # Current Temp (back to original position)
        draw.text((375, 35), f"{weather_data['temp_current']:.0f}°F", font=font160, fill=COLORS['black'])

        # "Now" and "Precip" to the right of temp
        draw.text((600, 60), f"Now: {weather_data['report']}", font=font22, fill=COLORS['black'], anchor="mm")  # Anchor middle-center
        draw.text((600, 110), f"Precip: {weather_data['precip_percent']:.0f}%", font=font30, fill=COLORS['black'], anchor="mm")

        # Rain forecast bars and timescale
        if weather_data['minutely_precipitation']:
            max_precipitation = max(weather_data['minutely_precipitation'])
            if max_precipitation > 0:
                bar_height_multiplier = 100 / max_precipitation
                bar_width = 5
                x_start = 345
                y_start = 450
                num_bars = len(weather_data['minutely_precipitation'])

                for i, precip in enumerate(weather_data['minutely_precipitation']):
                    bar_height = min(precip * bar_height_multiplier, 100)
                    draw.rectangle(
                        [(x_start + i * (bar_width + 2), y_start - bar_height),
                         (x_start + i * (bar_width + 2) + bar_width, y_start)],
                        fill=COLORS['black']
                    )

                now = datetime.now()
                for i in range(0, num_bars, 15):
                    time_label = (now + timedelta(minutes=i)).strftime('%I:%M')
                    draw.text((x_start + i * (bar_width + 2) - 10, y_start + 5), time_label, font=font_tiny, fill=COLORS['black'])

        # 5-Day Forecast Display
        x_offset = 345
        y_offset = 200
        day_spacing = 90

        for i, day_data in enumerate(weather_data['daily_forecast']):
            draw.text((x_offset + i * day_spacing, y_offset), day_data['date'], font=font24, fill=COLORS['black'])
            icon_forecast_path = os.path.join(ICON_DIR, f"{day_data['icon_code']}.png")
            if os.path.exists(icon_forecast_path):
                icon_forecast_image = Image.open(icon_forecast_path)
                icon_forecast_image = icon_forecast_image.resize((32, 32))
                template.paste(icon_forecast_image, (x_offset + i * day_spacing + 20, y_offset + 25))
            draw.text((x_offset + i * day_spacing, y_offset + 60), f"{day_data['temp_max']:.0f}°/{day_data['temp_min']:.0f}°", font=font18, fill=COLORS['black'])

        # Time updated
        current_time = datetime.now().strftime('%I:%M %p')
        draw.text((720, 10), current_time, font=font_small, fill=COLORS['black'])

        # Bottom-left corner information
        sunrise_time = datetime.fromtimestamp(weather_data['sunrise']).strftime('%I:%M %p')
        sunset_time = datetime.fromtimestamp(weather_data['sunset']).strftime('%I:%M %p')
        uvi_string = f"UV Index: {weather_data['uvi']}"

        y_info = 200
        draw.text((10, y_info), f"Sunrise: {sunrise_time}", font=font22, fill=COLORS['black'])
        draw.text((10, y_info + 40), f"Sunset: {sunset_time}", font=font22, fill=COLORS['black'])
        draw.text((10, y_info + 80), uvi_string, font=font22, fill=COLORS['black'])
        draw.text((10, y_info + 120), LOCATION, font=font_location, fill=COLORS['black'])

        # High/Low below other info
        draw.text((10, y_info + 160), f"High: {weather_data['temp_max']:.0f}°F", font=font40, fill=COLORS['black'])
        draw.text((10, y_info + 200), f"Low: {weather_data['temp_min']:.0f}°F", font=font40, fill=COLORS['black'])

        return template
    except Exception as e:
        logging.error(f"Error generating display image: {e}")
        raise

# Display image
def display_image(image):
    try:
        epd.display(epd.getbuffer(image))
        logging.info("Image displayed successfully.")
    except Exception as e:
        logging.error(f"Failed to display image: {e}")
        raise

# Main function
def main():
    try:
        data = fetch_weather_data()
        weather_data = process_weather_data(data)
        image = generate_display_image(weather_data)
        display_image(image)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
