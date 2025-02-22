import os
import sys
import csv
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import requests

# Automatically add the 'lib' directory relative to the script's location
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, 'lib')
sys.path.append(lib_path)
from waveshare_epd import epd7in5_V2
epd = epd7in5_V2.EPD()

# User defined configuration
API_KEY = 'XXXXXXXX'  # Your API key for openweathermap.com
LOCATION = 'XXXXXXXX'  # Name of location
LATITUDE = 'XXXXXXXX'  # Latitude
LONGITUDE = 'XXXXXXXX'  # Longitude
UNITS = 'imperial'  # imperial or metric
CSV_OPTION = True  # if csv_option == True, a weather data will be appended to 'record.csv'

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
font18 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 18)  # Smaller font for forecast
font22 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 22)
font30 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 30)
font35 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 35)
font50 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 50)
font100 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 100)
font160 = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 160)
font_small = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 20)
font_tiny = ImageFont.truetype(os.path.join(FONT_DIR, 'Font.ttc'), 14)

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
        daily = data['daily']  # Get the full daily forecast
        minutely = data.get('minutely', [])

        weather_data = {
            "temp_current": current['temp'],
            "feels_like": current['feels_like'], #Keep feels like for processing.
            "report": current['weather'][0]['description'].title(),
            "icon_code": current['weather'][0]['icon'],
            "temp_max": daily[0]['temp']['max'],  # Today's high
            "temp_min": daily[0]['temp']['min'],  # Today's low
            "precip_percent": daily[0]['pop'] * 100,  # Today's precip
            "minutely_precipitation": [minute['precipitation'] for minute in minutely] if minutely else [],
            "daily_forecast": []  # Initialize the list for the forecast
        }
        # Extract forecast for the next 5 days (including today)
        for day_data in daily[:5]:  # Get the first 5 days
            forecast_entry = {
                "date": datetime.fromtimestamp(day_data['dt']).strftime('%a'),  # Day of the week (e.g., "Mon")
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

# Save weather data to CSV (modified to include forecast)
def save_to_csv(weather_data):
    if not CSV_OPTION:
        return
    try:
        with open('records.csv', 'a', newline='') as csv_file:
            writer = csv.writer(csv_file)
            # Write current weather data + forecast data.  This is a bit verbose, but clear.
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M'),
                LOCATION,
                weather_data["temp_current"],
                weather_data["feels_like"],
                weather_data["temp_max"],
                weather_data["temp_min"],
                weather_data["precip_percent"],
                *[f"{day['date']}: {day['temp_max']:.0f}/{day['temp_min']:.0f} - {day['description']}" for day in weather_data["daily_forecast"]] # Forecast in one column
            ])
        logging.info("Weather data appended to CSV.")
    except IOError as e:
        logging.error(f"Failed to save data to CSV: {e}")

# Generate display image
def generate_display_image(weather_data):
    try:
        template = Image.open(os.path.join(PIC_DIR, 'template.png'))
        draw = ImageDraw.Draw(template)
        icon_path = os.path.join(ICON_DIR, f"{weather_data['icon_code']}.png")
        icon_image = Image.open(icon_path) if os.path.exists(icon_path) else None

        if icon_image:
            template.paste(icon_image, (40, 15))

        draw.text((30, 200), f"Now: {weather_data['report']}", font=font22, fill=COLORS['black'])
        draw.text((30, 240), f"Precip: {weather_data['precip_percent']:.0f}%", font=font30, fill=COLORS['black'])
        draw.text((375, 35), f"{weather_data['temp_current']:.0f}°F", font=font160, fill=COLORS['black'])
        # Removed feels like text
        draw.text((35, 325), f"High: {weather_data['temp_max']:.0f}°F", font=font50, fill=COLORS['black'])
        draw.text((35, 390), f"Low: {weather_data['temp_min']:.0f}°F", font=font50, fill=COLORS['black'])

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
                    draw.text((x_start + i * (bar_width + 2) -10, y_start + 5), time_label, font=font_tiny, fill=COLORS['black'])

        # 5-Day Forecast Display
        x_offset = 350  # Starting X position for the forecast
        y_offset = 200  # Starting Y position for the forecast
        day_spacing = 90

        for i, day_data in enumerate(weather_data['daily_forecast']):
            draw.text((x_offset + i * day_spacing, y_offset), day_data['date'], font=font18, fill=COLORS['black'])

            # Load and display the forecast icon
            icon_forecast_path = os.path.join(ICON_DIR, f"{day_data['icon_code']}.png")
            if os.path.exists(icon_forecast_path):
                icon_forecast_image = Image.open(icon_forecast_path)
                icon_forecast_image = icon_forecast_image.resize((32, 32))  # Resize for consistency
                template.paste(icon_forecast_image, (x_offset + i * day_spacing + 20, y_offset + 25)) # Adjusted for icon
            draw.text((x_offset + i* day_spacing, y_offset + 60), f"{day_data['temp_max']:.0f}°/{day_data['temp_min']:.0f}°", font=font18, fill=COLORS['black'])



        # Time updated
        current_time = datetime.now().strftime('%I:%M %p')
        draw.text((720, 10), current_time, font=font_small, fill=COLORS['black'])

        return template
    except Exception as e:
        logging.error(f"Error generating display image: {e}")
        raise

# Display image
def display_image(image):
    try:
        h_image = Image.new('1', (epd.width, epd.height), 255)
        h_image.paste(image, (0, 0))
        epd.display(epd.getbuffer(h_image))
        logging.info("Image displayed successfully.")
    except Exception as e:
        logging.error(f"Failed to display image: {e}")
        raise

# Main function
def main():
    try:
        data = fetch_weather_data()
        weather_data = process_weather_data(data)
        save_to_csv(weather_data)
        image = generate_display_image(weather_data)
        display_image(image)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
