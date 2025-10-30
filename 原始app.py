# app.py 完整修改版
from collections import Counter
from flask import Flask, render_template, request, send_file, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import json
import os
import shutil
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, text, inspect
import warnings
from flask_admin import Admin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    current_user, login_required
)

warnings.filterwarnings('ignore')

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = 'jhd783hdsajd7382hdsajkhds' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1464636102@localhost:3306/tibet2?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx'}
app.config['STATIC_FOLDER'] = 'static'

# 确保目录存在
for folder in [app.config['UPLOAD_FOLDER'], app.config['STATIC_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

db = SQLAlchemy(app)

# ===== 用户 & 登录 =====
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=True)
    def set_password(self, raw): self.password_hash = generate_password_hash(raw)
    def check_password(self, raw): return check_password_hash(self.password_hash, raw)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "请先登录。"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

# ===== 小工具 =====
def get_engine():
    return create_engine(app.config['SQLALCHEMY_DATABASE_URI'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.context_processor
def inject_global_vars():
    return {"current_date": datetime.now().strftime("%Y-%m-%d")}
from flask import Flask, render_template, request, send_file, redirect, url_for, send_from_directory, flash
# ===== 登录/登出/初始化管理员 =====
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        user = User.query.filter_by(username=username).first()
        if user and user.is_admin and user.check_password(password):
            login_user(user, remember=bool(request.form.get('remember')))
            return redirect(request.args.get('next') or url_for('home'))
        flash('账号或密码错误，或无管理员权限。', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
''''''
@app.route('/init-admin')
def init_admin():
    if User.query.filter_by(username='admin').first():
        return "已存在 admin 用户。"
    u = User(username='admin', is_admin=True)
    u.set_password('123456')  # 上线务必删除此路由并修改密码
    db.session.add(u); db.session.commit()
    return "管理员已创建：admin / 12345678"

# ===== 顶部导航与主页 =====
@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/home')
@login_required
def home():
    return render_template('home.html')
@app.route('/data-input')
def data_input():
    """数据输入界面"""
    return render_template('data_input.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            return redirect(request.url)
        
        try:
            # 保存上传文件
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 处理数据合并
            engine = get_engine()
            new_data = pd.read_excel(filepath)
            
            with engine.begin() as conn:
                # 创建临时表
                new_data.to_sql(
                    'temp_ffq',
                    conn,
                    if_exists='replace',
                    index=False,
                    dtype={'ID': db.String(255)}
                )

                # 合并数据
                inspector = inspect(conn)
                target_columns = [f"`{col['name']}`" for col in inspector.get_columns('ffq')]
                columns_str = ', '.join(target_columns)

                # 执行SQL
                conn.execute(text(
                    f"REPLACE INTO `ffq` ({columns_str}) "
                    f"SELECT {columns_str} FROM `temp_ffq`"
                ))
                conn.execute(text("DROP TABLE IF EXISTS temp_ffq"))

            # 执行营养计算
            from diet_nutrition_analysis import process_nutrition
            results, _, network_path = process_nutrition(engine, app.config['STATIC_FOLDER'])
            
            # 更新营养数据表
            results.to_sql('ffqnutrition', engine, if_exists='replace', index=False)
            
            # 移动网络图文件
            if network_path and os.path.exists(network_path):
                static_network = os.path.join(app.config['STATIC_FOLDER'], 'network.png')
                temp_dir = os.path.dirname(network_path)
                
                if os.path.exists(static_network):
                    os.remove(static_network)
                
                shutil.move(network_path, static_network)
                shutil.rmtree(temp_dir)
            
            return redirect(url_for('visualization'))
            
        except Exception as e:
            return f"处理失败: {str(e)}", 500
    
    return render_template('data_input.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """静态文件访问路由"""
    return send_from_directory(app.config['STATIC_FOLDER'], filename)


from werkzeug.utils import secure_filename
from flask import redirect, url_for
from ffq_nutrition_calculator import process_ffq_nutrition
from three_day_24h_nutrition_calculator import process_24h_nutrition
from evaluate_nutrient_qualification import evaluate_nutrient_qualification
from FFQfoodcount import calculate_food_categories
from PCA_die_pattern import calculate_pca
from validate_ffq_summary_with_diff_test import validate_ffq_summary
from services.dr24_merge import process_dr_uploads_and_merge
from calculate_web_dr_nutrients import process_web_dr_nutrition
from services.ffq_merge import process_ffq_uploads_and_merge

@app.route('/data_analysis', methods=['GET', 'POST'])
def data_analysis():
    if request.method == 'POST':
        analysis_type = request.form.get('analysis_type')

        # ====== A) DR-24 多文件合并（输出 ZIP）======
        if analysis_type == 'concat_dr':
            files = request.files.getlist('files')  # 表单里 name="files" multiple
            if not files or all(f.filename == '' for f in files):
                return "没有选择任何Excel文件", 400

            fixed = "fixed_divisor_3" in request.form  # 是否固定/3
            os.makedirs('downloads', exist_ok=True)

            zip_buf = process_dr_uploads_and_merge(files, fixed_divisor_3=fixed)
            zip_path = os.path.join('downloads', 'DR24_合并结果.zip')
            with open(zip_path, 'wb') as f:
                f.write(zip_buf.getvalue())

            return redirect(url_for('data_analysis', done='dr24_zip'))

        # ====== B) FFQ 多文件合并（输出单一 EXCEL）======
        if analysis_type == 'ffq_merge':
            files = request.files.getlist('files')  # 表单里 name="files" multiple
            if not files or all(f.filename == '' for f in files):
                return "没有选择任何Excel文件", 400

            os.makedirs('downloads', exist_ok=True)

            # header_row=2 是你的问卷表头在第3行，如有差异这里改
            xlsx_buf = process_ffq_uploads_and_merge(files, header_row=2)
            xlsx_path = os.path.join('downloads', 'FFQ_合并结果.xlsx')
            with open(xlsx_path, 'wb') as f:
                f.write(xlsx_buf.getvalue())

            return redirect(url_for('data_analysis', done='ffq_merge'))

        # ====== C) 其他分析（单文件上传）======
        if 'file' not in request.files:
            return "没有找到上传文件", 400
        file = request.files['file']
        if file.filename == '':
            return "没有选择文件", 400
        if not allowed_file(file.filename):
            return "文件类型不被允许", 400

        filename = secure_filename(file.filename)
        temp_path = os.path.join('uploads', filename)
        os.makedirs('uploads', exist_ok=True)
        file.save(temp_path)

        try:
            if analysis_type == 'ffq':
                output_path = os.path.join('downloads', 'ffq_nutrition_result.xlsx')
                os.makedirs('downloads', exist_ok=True)
                process_ffq_nutrition(temp_path, output_path)
                return redirect(url_for('data_analysis', done='ffq'))

            elif analysis_type == '24h':
                output_path = os.path.join('downloads', '24h_nutrition_result.xlsx')
                os.makedirs('downloads', exist_ok=True)
                process_24h_nutrition(temp_path, output_path)
                return redirect(url_for('data_analysis', done='24h'))

            elif analysis_type == 'assessment':
                output_path = os.path.join('downloads', 'nutrient_assessment_result.xlsx')
                evaluate_nutrient_qualification(temp_path, output_path)
                return redirect(url_for('data_analysis', done='assessment'))
            
            elif analysis_type == 'ffq_category':
                output_path = os.path.join('downloads', 'ffq_category_result.xlsx')
                calculate_food_categories(temp_path, output_path)
                return redirect(url_for('data_analysis', done='ffq_category'))

            elif analysis_type == 'pca_pattern':
                output_path = os.path.join('downloads', 'pca_pattern_result.xlsx')
                calculate_pca(temp_path, output_path)
                return redirect(url_for('data_analysis', done='pca_pattern'))

            elif analysis_type == 'validation_ffq':
                output_path = os.path.join('downloads', 'validation_ffq.xlsx')
                validate_ffq_summary(temp_path, output_path)
                return redirect(url_for('data_analysis', done='validation_ffq'))

            elif analysis_type == 'sum_dr_nutrients_for_web':
                output_path = os.path.join('downloads', 'sum_dr_nutrients_for_web.xlsx')
                process_web_dr_nutrition(temp_path, output_path)
                return redirect(url_for('data_analysis', done='sum_dr_nutrients_for_web'))

            else:
                return "未知分析类型", 400

        except Exception as e:
            return f"处理失败: {str(e)}", 500

    return render_template('data_analysis.html')




from flask import render_template, url_for

@app.route("/survey/dr24/raw")
def survey_dr24_raw():
    # 直接输出离线问卷整页（不套平台样式）
    return render_template("forms/dr24_raw.html")

@app.route("/survey/dr24")
def survey_dr24():
    # 用平台紫黑外壳 iframe 嵌入
    return render_template("survey_embed.html",
                           src=url_for("survey_dr24_raw"),
                           title="DR-24问卷")


@app.route("/survey/ffq/raw")
def survey_full_ffQ_raw():
    # 直接输出离线问卷整页（不套平台样式）
    return render_template("forms/Full-ffq.html")

@app.route("/survey/ffq")
def survey_full_ffQ():
    # 用平台紫黑外壳 iframe 嵌入
    return render_template("survey_embed copy.html",
                           src=url_for("survey_full_ffQ_raw"),
                           title="Full-FFQ问卷")

@app.route("/survey/sffq/raw")
def survey_S_ffQ_raw():
    # 直接输出离线问卷整页（不套平台样式）
    return render_template("forms/S-ffq.html")

@app.route("/survey/sffq")
def survey_S_ffQ():
    # 用平台紫黑外壳 iframe 嵌入
    return render_template("survey_embed copy 2.html",
                           src=url_for("survey_S_ffQ_raw"),
                           title="S-FFQ问卷")

@app.route('/download/<filetype>')
def download_file(filetype):
    if filetype == 'ffq':
        path = os.path.join('downloads', 'ffq_nutrition_result.xlsx')
        name = 'ffq_nutrition_result.xlsx'
    elif filetype == '24h':
        path = os.path.join('downloads', '24h_nutrition_result.xlsx')
        name = '24h_nutrition_result.xlsx'
    elif filetype == 'assessment': 
        path = os.path.join('downloads', 'nutrient_assessment_result.xlsx')
        name = 'nutrient_assessment_result.xlsx'
    elif filetype == 'ffq_category':  
        path = os.path.join('downloads', 'ffq_category_result.xlsx')
        name = 'ffq_category_result.xlsx'
    elif filetype == 'pca_pattern':  
        path = os.path.join('downloads', 'pca_pattern_result.xlsx')
        name = 'pca_pattern_result.xlsx'
    elif filetype == 'validation_ffq':  
        path = os.path.join('downloads', 'validation_ffq.xlsx')
        name = 'validation_ffq.xlsx'
    elif filetype == 'sum_dr_nutrients_for_web':
        path = os.path.join('downloads', 'sum_dr_nutrients_for_web.xlsx')
        name = 'sum_dr_nutrients_for_web.xlsx'

    elif filetype == 'dr24_zip':
        path = os.path.join('downloads', 'DR24_合并结果.zip')
        name = 'DR24_合并结果.zip'   
    elif filetype == 'ffq_merge':
        path = os.path.join('downloads', 'FFQ_合并结果.xlsx')
        name = 'FFQ_合并结果.xlsx'    
    else:
        return "无效文件类型", 400

    return send_file(path, as_attachment=True, download_name=name)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# 👇 引入封装模块
from admin_panel import setup_admin
setup_admin(app, db)

@app.route('/data_manage')
def data_manage():
    return redirect(url_for('admin.index'))


from flask import render_template
from sqlalchemy import func
# 放在 app.py 顶部（Flask 和 db 初始化后）
from sqlalchemy.ext.automap import automap_base
Base = automap_base()
with app.app_context():
    Base.prepare(db.engine, reflect=True)
    BasicInformation = Base.classes.basicinformation
    Disease = Base.classes.disease


from flask import render_template, send_file
from io import BytesIO
import base64
import diet_nutrition_analysis as dna
import plotly.graph_objects as go  # 标准导入方式
# ……其他表
@app.route('/visualization', methods=['GET'])
def visualization():
    # 查询样本总数
    total_samples = db.session.query(func.count()).select_from(BasicInformation).scalar()
    valid_samples = db.session.query(func.count()).filter(
        Disease.成人高血压.isnot(None)  # 排除NULL值
    ).scalar()

    # 获取高血压阳性数
    hypertension_count = db.session.query(func.count()).filter(
        Disease.成人高血压 == '是'  # 根据实际字段类型调整
    ).scalar()
    hypertension_rate = round((hypertension_count / valid_samples) * 100, 1) if valid_samples > 0 else 0.0

    return render_template('visualization.html',total_samples=total_samples,hypertension_rate=hypertension_rate)



if __name__ == '__main__':
    app.run(debug=True)


    
