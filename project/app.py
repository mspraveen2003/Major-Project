from flask import Flask, request, jsonify
import googlemaps
from datetime import datetime, timedelta

# Initialize Flask app and Google Maps client
app = Flask(__name__)
API_KEY = "AIzaSyCjZi8-iB7RXkSldq-MkaIhw2QIQX9SoQ0"  # Replace with your API key
gmaps = googlemaps.Client(key=API_KEY)

# Dictionary to track booked slots
booked_slots = {}

# Generate predefined time slots for appointments (9 AM to 6 PM)
def generate_time_slots(start_hour=9, end_hour=18):
    """Generate 30-minute time slots for a working day."""
    current_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end_time = datetime.now().replace(hour=end_hour, minute=0, second=0, microsecond=0)
    time_slots = []
    while current_time < end_time:
        time_slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=30)
    return time_slots

# Get latitude and longitude for a location
def get_coordinates(location_name):
    """Geocode a location into latitude and longitude."""
    try:
        geocode_result = gmaps.geocode(location_name)
        if geocode_result:
            location = geocode_result[0]["geometry"]["location"]
            return location["lat"], location["lng"]
    except Exception as e:
        print(f"Error fetching coordinates for {location_name}: {e}")
    return None

# Fetch nearby places using Google Maps API
def fetch_nearby_places(user_location, radius=5000, keyword="place"):
    """Fetch places nearby based on a keyword."""
    try:
        places_result = gmaps.places_nearby(
            location=user_location, radius=radius, keyword=keyword
        )
        return [
            {
                "name": place["name"],
                "address": place["vicinity"],
                "location": (
                    place["geometry"]["location"]["lat"],
                    place["geometry"]["location"]["lng"],
                ),
            }
            for place in places_result.get("results", [])
        ]
    except Exception as e:
        print(f"Error fetching nearby {keyword}: {e}")
        return []

@app.route('/find', methods=['POST'])
def find_places():
    """API to fetch nearby places."""
    data = request.json
    location = data.get('location')
    service = data.get('service')

    user_location = get_coordinates(location)
    if not user_location:
        return jsonify({'error': 'Invalid location'}), 400

    places = fetch_nearby_places(user_location, keyword=service)
    if not places:
        return jsonify({'error': f'No {service} found nearby.'}), 404

    return jsonify({'places': places})

@app.route('/book', methods=['POST'])
def book_appointment():
    """API to book an appointment."""
    data = request.json
    place_name = data.get('place')
    time_slot = data.get('time_slot')

    if not place_name or not time_slot:
        return jsonify({'error': 'Place and time slot are required'}), 400

    if place_name not in booked_slots:
        booked_slots[place_name] = []

    if time_slot in booked_slots[place_name]:
        return jsonify({'error': 'Time slot already booked'}), 409

    booked_slots[place_name].append(time_slot)
    return jsonify({'message': f'Appointment booked successfully at {place_name} for {time_slot}!'})

@app.route('/slots', methods=['GET'])
def get_time_slots():
    """API to fetch available time slots."""
    place_name = request.args.get('place')
    if not place_name:
        return jsonify({'error': 'Place is required'}), 400

    all_time_slots = generate_time_slots()
    booked_time_slots = booked_slots.get(place_name, [])
    available_slots = [slot for slot in all_time_slots if slot not in booked_time_slots]

    return jsonify({'available_slots': available_slots})

if __name__ == '__main__':
    app.run(debug=True)
