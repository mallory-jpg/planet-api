from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
from flask_mail import Mail, Message
import os

from schema import *
from db_models import *

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__)) # path for application == path for db

# add config variables
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'planets.db') # creates db called 'planets'
app.config['JWT_SECRET_KEY'] = 'super_secret' # should be changed in production
# configure email server at mailtrap.io / set environment variables
app.config['MAIL_SERVER']='smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = os.environ['MAIL_USERNAME']
app.config['MAIL_PASSWORD'] = os.environ['MAIL_PASSWORD']
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False


# initialize db
db = SQLAlchemy(app)
# instantiate Marshmallow class
ma = Marshmallow(app)
# instantiate JWT Manager class
jwt = JWTManager(app)
mail = Mail(app)

# CLI commands
@app.cli.command('db_create')
def db_create():
    db.create_all()
    print('Database created')

@app.cli.command('db_drop')
def db_drop():
    db.drop_all()
    print('Database destroyed')

@app.cli.command('db_seed')
def db_seed():
    mercury = Planet(planet_name='Mercury', 
                    planet_type='Class D', 
                    home_star='Sol',
                    mass=3.258e23,
                    radius=1516,
                    distance=35.98e6)
    
    venus = Planet(planet_name='Venus', 
                    planet_type='Class K', 
                    home_star='Sol',
                    mass=4.867e24,
                    radius=3760,
                    distance=67.24e6)
    
    earth = Planet(planet_name='Earth', 
                    planet_type='Class M', 
                    home_star='Sol',
                    mass=5.972e24,
                    radius=3959,
                    distance=92.96e6)
    
    db.session.add(mercury)
    db.session.add(venus)
    db.session.add(earth)

    test_user = User(first_name='Mallory',
                    last_name='Culbert',
                    email='foo@bar.com',
                    password='pass')
    
    db.session.add(test_user)
    db.session.commit()
    print('Database seeded')


@app.route('/')
def hello_world():
    return jsonify(message='Hello from Planetary API')

@app.route('/not_found')
def not_found():
    return jsonify(message='That resource was not found.'), 404

@app.route('/params')
def params():
    """Use request object to get to key-value pairs"""
    # example end url: http://localhost:5000/params?name=Mallory&age=16
    name = request.args['name']
    age = int(request.args['age'])
    if age < 18:
        return jsonify(message=f'Sorry, {name}, you are not old enough'), 401 # return 401 status code
    else:
        return jsonify(message=f'Welcome {name}, you are old enough!')


@app.route('/url_variables/<string:name>/<int:age>')
def url_variables(name:str, age:int):
    """Use variable-rule matching to parse url itself"""
    # example end url: http://localhost:5000/url_variables/Mallory/24
    if age < 18:
        return jsonify(message=f'Sorry, {name}, you are not old enough'), 401 # return 401 status code
    else:
        return jsonify(message=f'Welcome {name}, you are old enough!')


@app.route('/planets', methods=['GET']) # specify rule to only acces GET requests
def planets():
    planets_list = Planet.query.all()
    # deserialize result using Marshmallow
    result = planets_schema.dump(planets_list)
    # jsonify
    return jsonify(result)


@app.route('/register', methods=['POST'])
def register():
    email = request.form['email']
    # check if user exists
    test = User.query.filter_by(email='email').first()
    if test:
        return jsonify(message='That email already exists!'), 409
    else:
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        password = request.form['password']
        user = User(first_name=first_name, last_name=last_name, email=email, password=password)

        db.session.add(user)
        db.session.commit()

        return jsonify(message='User created successfully.'), 201

@app.route('/login', methods=['POST']) # POST used for logins!
def login():
    if request.is_json:
        email = request.json['email']
        password = request.json['password']
    else:
        email = request.form['email']
        password = request.form['password']
    
    test = User.query.filter_by(email=email, password=password).first() # get first unique entry
    if test: # login exists
        access_token = create_access_token(identity=email) # using email to identify user
        return jsonify(message='Login succeeded!', access_token=access_token)
    else:
        return jsonify(message='Bad email or password. Try again.'), 401

@app.route('/retrieve_password/<string:email>', methods=['GET'])
def retrieve_password(email:str):
    user = User.query.filter_by(email=email).first()
    if user:
        msg = Message(f'Your PlanetaryAPI password is {user.password}', sender='admin@api.com', recipients=[email])
        mail.send(msg)
        return jsonify(message=f'Password sent to {email}')
    else:
        return jsonify(message=f'That email doesn\'t exist'), 401

@app.route('/planet_details/<int:planet_id>', methods=['GET'])
def planet_details(planet_id:int):
    planet = Planet.query.filter_by(planet_id=planet_id).first()
    if planet:
        result = planet_schema.dump(planet)
        return jsonify(result)
    else:
        return jsonify(message=f'That planet does not exist'), 404

@app.route('/add_planet', methods=['POST'])
@jwt_required() # secures endpoint - requires JWT login to use
def add_planet():
    planet_name = request.form['planet_name']
    test = Planet.query.filter_by(planet_name=planet_name).first()
    if test:
        return jsonify(message='There is already a planet by that name. Try again.'), 409
    else:
        planet_type = request.form['planet_type']
        home_star = request.form['home_star']
        mass = float(request.form['mass'])
        radius = float(request.form['radius'])
        distance = float(request.form['distance'])
        new_planet = Planet(planet_name=planet_name,
                            planet_type=planet_type, 
                            home_star=home_star, 
                            mass=mass, 
                            radius=radius, 
                            distance=distance
                        )
        db.session.add(new_planet)
        db.session.commit()
        return jsonify(message=f'You have added a planet: {new_planet.planet_name}, the first of its name.')

@app.route('/update_planet', methods=['PUT'])
@jwt_required()
def update_planet():
    planet_id = int(request.form['planet_id'])
    planet = Planet.query.filter_by(planet_id='planet_id').first()
    if planet:
        planet.planet_name = request.form['planet_name']
        planet.planet_type = request.form['planet_type']
        planet.mass = float(request.form['home_star'])
        planet.radius = float(request.form['radius'])
        planet.distance = float(request.form['distance'])

        db.session.commit()
        return jsonify(message=f'You updated planet number {planet_id}!')
    else:
        return jsonify(message='That planet does not exist.')

@app.route('/remove_planet/<int:planet_id>', methods=['DEL'])
@jwt_required()
def remove_planet(planet_id:int):
    planet = Planet.query.filter_by(planet_id).first()
    if planet:
        db.session.delete(planet)
        db.session.commit()
        return jsonify(message=f'You deleted {planet.planet_name}'), 201
    else:
        return jsonify(message='That planet does not exist.'), 404


user_schema = UserSchema() # deserialize one object
users_schema = UserSchema(many=True) # deserialize multiple records

planet_schema = PlanetSchema()
planets_schema = PlanetSchema(many=True)


if __name__ == '__main__':
    app.run()