from geopy.distance import geodesic
import sqlite3
import bcrypt
from datetime import datetime
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import googlemaps
import json


app = Flask(__name__)
app.secret_key = 'SHAAN'
my_secret = os.environ['GooglemapsAPI']
app.config[my_secret] = os.environ.get('GooglemapsAPI')
db_path = 'database.db'
gmaps = googlemaps.Client(key='AIzaSyDYy2MLowsg4DUg4iakgE53D-yhFk78rhQ')

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def home():
    return render_template('homep.html')


@app.route('/Login', methods=['GET', 'POST'])
def Login():
    return render_template('loginp.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login_input = data.get('phone')
    otp = data.get('otp')

    conn = get_db_connection()
    c = conn.cursor()

    # Check if the username exists in the Provider table
    c.execute("SELECT * FROM Provider WHERE PhoneNumber = ?", (login_input, ))
    provider = c.fetchone()

    if provider:
        # Check if the provided OTP matches the static OTP "1234"
        if otp == '1234':
            # Set session variables
            session['provider_id'] = provider['ID']  # Store user ID in session
            conn.close()
            return jsonify({'message': 'Login successful!'})
        else:
            conn.close()
            return jsonify({'message': 'Invalid OTP entered.'}), 401
    else:
        conn.close()
        return jsonify({'message': 'User not registered'}), 401


@app.route('/home1')
def home1():
    provider_id = session.get('provider_id')
    if not provider_id:
        return redirect(
            url_for('Login'))  # Redirect to login if user is not logged in

    conn = get_db_connection()
    provider = conn.execute('SELECT * FROM Provider WHERE ID = ?',
                            (provider_id, )).fetchone()
    conn.close()

    if provider is None:
        return redirect(url_for(
            'Login'))  # Redirect to login if user or provider is not found

    user_initial = provider['FirstName'][0].upper(
    ) + provider['LastName'][0].upper()

    return render_template('home1p.html',
                           provider=provider,
                           user_initial=user_initial)


@app.route('/logout', methods=['GET'])
def logout():
    # Clear the session (logout user)
    session.clear()
    # Invalidate cache
    response = redirect(url_for('home'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.after_request
def add_cache_control(response):
    if 'provider_id' in session:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.route('/account_details')
def account_details():
    provider_id = session.get('provider_id')
    if not provider_id:
        return redirect(
            url_for('login'))  # Redirect to login if user is not logged in

    conn = get_db_connection()
    provider = conn.execute('SELECT * FROM Provider WHERE ID = ?',
                            (provider_id, )).fetchone()
    conn.close()

    if not provider:
        return redirect(
            url_for('login'))  # Redirect to login if user is not found

    return render_template('AccountDetails.html', provider=provider)


@app.route('/update_provider', methods=['POST'])
def update_provider():
    provider_id = session.get('provider_id')
    if not provider_id:
        return jsonify({'message': 'User not logged in!'}), 401

    try:
        # Extract data from the form
        first_name = request.form['firstname']
        last_name = request.form['lastname']
        address = request.form['address']
        phone = request.form['phonenumber']
        email = request.form['email']
        vehicle_type = request.form['vehicle_type']
        cost_per_hour = request.form['cost_per_hour']

        conn = get_db_connection()
        c = conn.cursor()

        # Update provider details in the Provider table
        c.execute(
            '''
            UPDATE Provider 
            SET FirstName=?, LastName=?, Address=?, PhoneNumber=?, Email=?, VehicleType=?, CostPerHour=?
            WHERE ID=?
        ''', (first_name, last_name, address, phone, email, vehicle_type,
              cost_per_hour, provider_id))

        # Update provider details in the Booking table where the provider matches
        c.execute(
            '''
            UPDATE Booking 
            SET ProviderFirstName=?, ProviderLastName=?, ProviderAddress=?, VehicleType=?, CostPerHour=?
            WHERE ProviderFirstName=? AND ProviderLastName=? AND ProviderAddress=? AND VehicleType=? AND CostPerHour=?
        ''', (first_name, last_name, address, vehicle_type, cost_per_hour,
              first_name, last_name, address, vehicle_type, cost_per_hour))

        conn.commit()
        conn.close()

        return jsonify({'message': 'User details updated successfully!'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Failed to update user details!'}), 500

@app.route('/EnlistProperty', methods=['GET', 'POST'])
def EnlistProperty():
    is_logged_in = 'provider_id' in session
    return render_template('enlistproperty.html', my_secret=os.environ.get('GooglemapsAPI'), is_logged_in=is_logged_in)


# Geocode function to get latitude and longitude
def geocode_address(address):
    try:
        geocode_result = gmaps.geocode(address)

        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            return None, None
    except Exception as e:
        print(f"Error geocoding address: {e}")
        return None, None

@app.route('/enlistproperty', methods=['POST'])
def enlistproperty():
    if request.method == 'POST':
        try:
            create_tables()  # Ensure the Provider and Booking tables exist

            # Extract data from the form
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            address = request.form['address']
            phone = request.form['phone']
            email = request.form['email']
            vehicle_type = request.form['vehicle_type']
            cost_per_hour = float(request.form['cost_per_hour'])  # Convert to float

            # Geocode address to get latitude and longitude
            lat, lng = geocode_address(address)

            if lat is None or lng is None:
                return jsonify({'success': False, 'message': 'Failed to geocode the address!'}), 400

            conn = get_db_connection()
            c = conn.cursor()

            # Check if the property already exists
            c.execute("SELECT * FROM Provider WHERE Address = ?", (address,))
            existing_property = c.fetchone()
            if existing_property:
                conn.close()
                return jsonify({'success': False, 'message': 'Property already enlisted!'}), 409

            # Insert into Provider table in the database
            c.execute('''
                INSERT INTO Provider (FirstName, LastName, Address, lat, lng, PhoneNumber, Email, VehicleType, CostPerHour)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (first_name, last_name, address, lat, lng, phone, email, vehicle_type, cost_per_hour))


            conn.commit()
            conn.close()

            return jsonify({'success': True, 'message': 'Property enlisted successfully!'})
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({'success': False, 'message': 'Failed to enlist property!'}), 500

        return redirect(url_for('home1'))

@app.route('/delistproperty', methods=['GET', 'POST'])
def delistproperty():
    if 'phone_number' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    phone_number = session['phone_number']
    conn = get_db_connection()
    c = conn.cursor()

    if request.method == 'GET':
        # Fetch properties for the logged-in provider
        c.execute('''
            SELECT id, Address, VehicleType
            FROM Provider
            WHERE PhoneNumber = ?
        ''', (phone_number,))
        properties = c.fetchall()
        conn.close()
        return render_template('delistproperty.html', properties=properties, is_logged_in=True)

    elif request.method == 'POST':
        try:
            property_id = request.form['property_id']

            # Delete property from the Provider table
            c.execute('''
                DELETE FROM Provider
                WHERE id = ? AND PhoneNumber = ?
            ''', (property_id, phone_number))
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'message': 'Property delisted successfully!'})
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({'success': False, 'message': 'Failed to delist property!'}), 500


@app.route('/mybookings')
def my_bookings():
    provider_id = session.get('provider_id')
    if not provider_id:
        return redirect(url_for('Login'))  # Redirect to login if user is not logged in

    conn = get_db_connection()
    c = conn.cursor()

    # Fetch bookings for the current provider's address
    c.execute('''
        SELECT ProviderFirstName, ProviderLastName, ProviderAddress, VehicleType, BookingDate, BookingTime, TimeDuration, BookingAmount, Availability
        FROM Booking
        WHERE ProviderAddress = (
            SELECT Address FROM Provider WHERE ID = ?
        )
    ''', (provider_id,))
    bookings = c.fetchall()

    conn.close()

    return render_template('mybookings.html', bookings=bookings)



if __name__ == '__main__':
    app.run(debug=True)
