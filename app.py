from flask import Flask, jsonify, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# กำหนดค่าฐานข้อมูล
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config['SQLALCHEMY_BINDS'] = {
    'patients': 'sqlite:///info.db'  # ฐานข้อมูลสำหรับข้อมูลผู้ป่วย
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = '1234'  # สำหรับจัดการ session
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Patient(db.Model):
    __bind_key__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    surname = db.Column(db.String(150), nullable=False)
    dental_num = db.Column(db.String(50), nullable=False)
    diagnosis = db.Column(db.Text, nullable=True)  # เปลี่ยนเป็น Text เพื่อรองรับข้อมูลหลายรายการ
    icd10 = db.Column(db.Text, nullable=True)      # เปลี่ยนเป็น Text เช่นกัน
    visit_type = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.String(150), nullable=True)

    def add_diagnosis(self, diagnosis, icd_code):
        if self.diagnosis:
            self.diagnosis += f",{diagnosis}"
            self.icd10 += f",{icd_code}"
        else:
            self.diagnosis = diagnosis
            self.icd10 = icd_code


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_or_username = request.form['email_or_username']
        password = request.form['password']
        user = User.query.filter((User.email == email_or_username) | (User.username == email_or_username)).first()
        if user and user.check_password(password):
            session['username'] = user.username  # เก็บ username ใน session
            return jsonify(success=True)
        else:
            return jsonify(success=False, message="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง.")
        
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)  # ลบข้อมูล session ของ username
    return redirect(url_for('index'))

@app.context_processor
def inject_user():
    return dict(current_user=session.get('username'))

@app.route('/reg', methods=['GET', 'POST'])
def reg():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        username = request.form.get('username')

        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            return {"success": False, "message": "อีเมลหรือชื่อผู้ใช้นี้มีอยู่แล้ว."}, 400

        new_user = User(email=email, username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        return {"success": True, "message": "ลงทะเบียนสำเร็จ!"}, 200
    return render_template('reg.html')

@app.route('/main')
def main():
    patients = Patient.query.all()
    return render_template('main.html', patients=patients)

@app.route('/search')
def search():
    return render_template('search.html')

# ฟังก์ชันใหม่สำหรับค้นหาข้อมูล
@app.route('/search_results', methods=['POST'])
def search_results():
    data = request.get_json()
    filter_type = data.get("filterType")
    filter_value = data.get("filterValue", "").lower()

    query = db.session.query(Patient)

    if filter_type == "name":
        query = query.filter(Patient.name.ilike(f"%{filter_value}%"))
    elif filter_type == "surname":
        query = query.filter(Patient.surname.ilike(f"%{filter_value}%"))
    elif filter_type == "dental_number":
        query = query.filter(Patient.dental_num.ilike(f"%{filter_value}%"))
    elif filter_type == "diagnosis":
        query = query.filter(Patient.diagnosis.ilike(f"%{filter_value}%"))
    elif filter_type == "icd_10":
        query = query.filter(Patient.icd10.ilike(f"%{filter_value}%"))
    elif filter_type == "type_of_visit":
        query = query.filter(Patient.visit_type.ilike(f"%{filter_value}%"))
    elif filter_type == "date":
        try:
            search_date = datetime.strptime(filter_value, "%Y-%m-%d").date()
            query = query.filter(Patient.date == search_date)
        except ValueError:
            return jsonify([])

    results = []
    for patient in query.all():
        diagnoses = patient.diagnosis.split(",") if patient.diagnosis else ["-"]
        icd10_codes = patient.icd10.split(",") if patient.icd10 else ["-"]

        # ใช้ <br> แทนการคั่นด้วย comma
        diagnosis_text = "<br>".join(diagnoses).strip() if diagnoses else "-"
        icd_text = "<br>".join(icd10_codes).strip() if icd10_codes else "-"

        results.append({
            "name": patient.name,
            "surname": patient.surname,
            "dental_number": patient.dental_num,
            "diagnosis": diagnosis_text,
            "icd_10": icd_text,
            "type_of_visit": patient.visit_type,
            "date": patient.date.strftime("%Y-%m-%d") if patient.date else "-"
        })

    return jsonify(results)


@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        name = request.form.get('name')
        surname = request.form.get('surname')
        dental_num = request.form.get('dental_num')
        visit_type = request.form.get('visit_type')
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # เก็บชื่อผู้ใช้ที่เพิ่มข้อมูล
        created_by = session.get('username')  # ดึงข้อมูล username จาก session

        # เพิ่มผู้ป่วยใหม่และบันทึกชื่อผู้ใช้ที่ทำการเพิ่มข้อมูล
        new_patient = Patient(
            name=name,
            surname=surname,
            dental_num=dental_num,
            visit_type=visit_type,
            date=date,
            created_by=created_by
        )
        db.session.add(new_patient)
        db.session.commit()

        # เพิ่มการวินิจฉัยหลายรายการ
        diagnoses = request.form.getlist('diagnosis[]')
        icd10_codes = request.form.getlist('icd10[]')
        
        for diagnosis, icd10 in zip(diagnoses, icd10_codes):
            if diagnosis or icd10:
                new_patient.add_diagnosis(diagnosis, icd10)

        db.session.commit()
        flash('เพิ่มข้อมูลผู้ป่วยสำเร็จ!')
        return redirect(url_for('add'))

    return render_template('add.html')

# สร้างตารางฐานข้อมูลเมื่อเริ่มต้น
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)