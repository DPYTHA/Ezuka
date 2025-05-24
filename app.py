from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_mail import Mail, Message
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask_jwt_extended import jwt_required, get_jwt_identity
from config import Config
import os
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

import smtplib
from email.mime.text import MIMEText
from flask_cors import CORS
app = Flask(__name__) 
app.config.from_object(Config)
CORS(app)

# Load env vars
load_dotenv()

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

# Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
mail = Mail(app)

print("DATABASE_URL =", os.getenv("DATABASE_URL"))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    solde = db.Column(db.Float, default=0.0)
    role = db.Column(db.String(20), default='user')  # <-- Nouveau champ role



class Transfert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prenom_beneficiaire = db.Column(db.String(120), nullable=False)
    numero = db.Column(db.String(50), nullable=False)
    pays = db.Column(db.String(50), nullable=False)
    methode = db.Column(db.String(50), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    devise = db.Column(db.String(10), nullable=False)
    montant_recu = db.Column(db.Float, nullable=False)
   
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('transferts', lazy=True))
    date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# 📌 Modèle de données
class DepositIntent(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    method = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(50), nullable=False)  # ← Champ ajouté
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Fee(db.Model):
    __tablename__ = 'fees'
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String, unique=True, nullable=False)
    currency = db.Column(db.String, nullable=False)
    methods = db.Column(db.ARRAY(db.String), nullable=True)  # PostgreSQL ARRAY
    fee_rate = db.Column(db.Float, nullable=False)

class ExchangeRate(db.Model):
    __tablename__ = 'exchange_rates'
    id = db.Column(db.Integer, primary_key=True)
    source_currency = db.Column(db.String, nullable=False)
    target_currency = db.Column(db.String, nullable=False)
    rate = db.Column(db.Float, nullable=False)


@app.route("/")
def home():
    return "Backend Flask fonctionnel sur Render 🚀"


@app.route('/admin/fees', methods=['GET', 'POST'])
def manage_fees():
    if request.method == 'GET':
        fees = Fee.query.all()
        return jsonify([{
            'id': f.id,
            'country': f.country,
            'currency': f.currency,
            'methods': f.methods,
            'fee_rate': f.fee_rate
        } for f in fees])
    else:
        data = request.json
        fee = Fee.query.filter_by(country=data['country']).first()
        if fee:
            fee.fee_rate = data['fee_rate']
            db.session.commit()
            return jsonify({'message': 'Frais mis à jour'})
        return jsonify({'error': 'Pays introuvable'}), 404

@app.route('/admin/exchange-rates', methods=['GET', 'POST'])
def manage_exchange_rates():
    if request.method == 'GET':
        rates = ExchangeRate.query.all()
        return jsonify([{
            'id': r.id,
            'source_currency': r.source_currency,
            'target_currency': r.target_currency,
            'rate': r.rate
        } for r in rates])
    else:
        data = request.json
        rate = ExchangeRate.query.filter_by(
            source_currency=data['source_currency'],
            target_currency=data['target_currency']
        ).first()
        if rate:
            rate.rate = data['rate']
            db.session.commit()
            return jsonify({'message': 'Taux mis à jour'})
        return jsonify({'error': 'Taux introuvable'}), 404


# 🛠 Crée les tables une seule fois
with app.app_context():
    db.create_all()
# ROUTES
@app.route('/')
def home():
    return '✅ API de transfert opérationnelle'

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # Champs obligatoires
    required_fields = ['nom', 'prenom', 'email', 'phone', 'password', 'country']
    if not all(data.get(k) for k in required_fields):
        return jsonify({"message": "Tous les champs sont requis"}), 400

    # Vérification de l'unicité de l'email
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"message": "Utilisateur déjà existant"}), 400

    # Hachage sécurisé du mot de passe
    hashed_pw = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    data.pop('password')  # Supprimer le mot de passe en clair du dictionnaire

    # Optionnel : rôle par défaut
    role = data.get('role', 'user')  # ou impose 'user' directement

    # Création de l'utilisateur avec solde initial à 0.0
    user = User(**data, password=hashed_pw, solde=0.0, role=role)

    db.session.add(user)
    db.session.commit()

    # Envoi d’un message de bienvenue
    msg = Message(
        'Bienvenue sur E$UKA',
        sender=app.config['MAIL_USERNAME'],
        recipients=[user.email]
    )
    msg.body = f"Bonjour {user.prenom},\n\nBienvenue sur E$UKA !\n\nL’équipe E$UKA"
    mail.send(msg)

    return jsonify({"message": "Inscription réussie"}), 201


from flask import request, jsonify
from flask_jwt_extended import create_access_token

from flask import request, jsonify
from flask_jwt_extended import create_access_token


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Champs manquants'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Email ou mot de passe incorrect'}), 401

    # Vérification correcte du mot de passe
    if not bcrypt.check_password_hash(user.password, password):
        return jsonify({'message': 'Email ou mot de passe incorrect'}), 401

    # ✅ Corriger ici : identity doit être un str ou int (id ou email par exemple)
    token = create_access_token(identity=str(user.id))

    # Retourner le token et les infos
    return jsonify({
        'message': 'Connexion réussie',
        'prenom': user.prenom,
        'country': user.country,
        'role': user.role,
        'token': token
    }), 200


from flask import request, jsonify
from datetime import datetime, timezone
from flask_mail import Message

@app.route('/transfert', methods=['POST'])
def transfert():
    data = request.get_json()
    print("Données reçues pour /transfert:", data)
    print("Reçu:", data)
   

    champs_requis = ['prenom_beneficiaire', 'numero', 'pays', 'methode', 'montant', 'devise', 'email']
    missing_fields = [c for c in champs_requis if c not in data or str(data[c]).strip() == ""]
    if missing_fields:
        return jsonify({"error": f"Champs manquants ou vides : {missing_fields}"}), 400

    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    try:
        montant_envoye = float(data['montant'])
    except (ValueError, TypeError):
        return jsonify({"error": "Montant invalide"}), 400
    

    print("User:", user)
    print("Solde utilisateur:", user.solde)
    print("Montant envoyé:", montant_envoye)
    print("Devise:", data['devise'])
    print("Pays bénéficiaire:", data['pays'])
   

    if user.solde < montant_envoye:
        return jsonify({"error": "Solde insuffisant"}), 400

    country_currency = {
        'Côte d’Ivoire': 'FCFA',
        'Mali': 'FCFA',
        'Guinée': 'GNF',
        'Ghana': 'GHS',
        'Russie': 'RUB',
        'Benin': 'FCFA',
        'Togo': 'FCFA',
        'Burkina-Faso': 'FCFA',
        'Niger': 'FCFA',
        'Senegal': 'FCFA',
    }

    try:
        # Déterminer la devise cible
        devise_cible = country_currency.get(data['pays'], data['devise'])
        devise_source = data['devise']
        if devise_source == "XOF":
           devise_source = "FCFA"



        # Récupérer le taux de change
        rate = ExchangeRate.query.filter_by(
       source_currency=devise_source,
       target_currency=devise_cible
       ).first()
   

        if not rate:
            return jsonify({"error": "Taux de change introuvable"}), 404
        print("Taux:", rate.rate if rate else "Introuvable")

        # Calcul du montant reçu à partir du taux dynamique
        montant_recu = round(montant_envoye * rate.rate, 2)

        # Déduire le montant du solde de l'utilisateur
        user.solde -= montant_envoye

        # Création du transfert lié à l'utilisateur
        t = Transfert(
            prenom_beneficiaire=data['prenom_beneficiaire'],
            numero=data['numero'],
            pays=data['pays'],
            methode=data['methode'],
            montant=montant_envoye,
            devise=data['devise'],
            montant_recu=montant_recu,
            date=datetime.now(timezone.utc),
            user_id=user.id  # Liaison à l'utilisateur
        )

        db.session.add(t)
        db.session.commit()

        msg = Message(
            subject="📤 Nouveau Transfert",
            sender=app.config['MAIL_USERNAME'],
            recipients=[app.config['MAIL_USERNAME']]
        )
        msg.body = f"""
📤 Nouveau transfert :

👤 Bénéficiaire : {t.prenom_beneficiaire}
📞 Numéro : {t.numero}
🌍 Pays : {t.pays}
💳 Méthode : {t.methode}
💰 Envoyé : {t.montant} {t.devise}

💵 Reçu : {t.montant_recu} {devise_cible}
📅 Date : {t.date.strftime('%Y-%m-%d %H:%M:%S')}
"""
        mail.send(msg)

        return jsonify({
            "message": "Transfert enregistré avec succès ✅",
            "solde_restant": user.solde,
            "transfert": {
                "id": t.id,
                "montant_envoye": t.montant,
                "montant_recu": t.montant_recu,
                "devise": t.devise,
                "pays": t.pays,
                "date": t.date.strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"[Erreur Transfert] {e}")
        return jsonify({"error": "Erreur d'enregistrement"}), 500

#MesTransferts

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route('/mes-transferts', methods=['GET'])
@jwt_required()
def mes_transferts():
    try:
        user_id = get_jwt_identity()  # JWT identity is a string
        user = User.query.get(int(user_id))  # convert to int if needed

        if not user:
            return jsonify({"error": "Utilisateur introuvable"}), 404

        transferts = Transfert.query.filter_by(user_id=user.id).order_by(Transfert.date.desc()).all()

        transferts_data = [
            {
                "id": t.id,
                "prenom_beneficiaire": t.prenom_beneficiaire,
                "pays": t.pays,
                "methode": t.methode,
                "montant": t.montant,
                "devise": t.devise,
                "montant_recu": t.montant_recu,
                "numero": t.numero,
                "date": t.date.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for t in transferts
        ]

        return jsonify({"transferts": transferts_data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    #recuperer le solde

@app.route('/solde', methods=['GET'])
def get_solde():
    email = request.args.get('email')
    print("Requête solde pour email:", email)  # <- Debug
    if not email:
        return jsonify({'error': 'Email requis'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        print("Utilisateur non trouvé pour email:", email)  # <- Debug
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    print("Solde trouvé:", user.solde)  # <- Debug
    return jsonify({'solde': user.solde}), 200



#pour le depot.........

@app.route('/api/deposit-intent', methods=['POST'])
def deposit_intent():
    data = request.get_json()
    print("Données reçues pour /deposit-intent:", data)
    try:
        prenom = data.get('prenom')
        email = data.get('email')
        country = data.get('country')
        method = data.get('method')
        amount = data.get('amount')
        phone = data.get('phone')  # ← nouveau champ ajouté côté frontend

        if not all([prenom, email, country, method, amount, phone]):
            return jsonify({"error": "Tous les champs sont requis."}), 400

        new_intent = DepositIntent(
            prenom=prenom,
            email=email,
            country=country,
            method=method,
            amount=amount,
            phone=phone  # ← ajout dans la base de données
        )
        db.session.add(new_intent)
        db.session.commit()

        # Envoi email automatique
        msg = Message(
            subject="Nouvelle intention de dépôt",
            sender=app.config['MAIL_USERNAME'],
            recipients=["moua19878@gmail.com"],
            body=f"""
Nouvelle intention de dépôt :
Prénom : {prenom}
Email : {email}
Pays : {country}
Méthode : {method}
Montant : {amount}
Téléphone  : {phone}
"""
        )
        mail.send(msg)

        return jsonify({"message": "Intention envoyée avec succès."}), 200

    except Exception as e:
        print(f"Erreur: {e}")
        return jsonify({"error": "Erreur lors de l’envoi de l’intention"}), 500



#recuperation de solde 



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
