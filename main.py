from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from flask_wtf import FlaskForm
from wtforms import StringField, SelectMultipleField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = '123'  # Замените 'your_unique_secret_key' на уникальный и секретный ключ
db = SQLAlchemy(app)


class Results(db.Model):
    idResult = db.Column(db.Integer, primary_key=True)
    result = db.Column(db.Integer, nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.testId'), nullable=False)
    test = db.relationship('Tests', back_populates='results')

class Tests(db.Model):
    testId = db.Column(db.Integer, primary_key=True)
    test_name = db.Column(db.String(100), nullable=False, unique=True)
    questions = db.relationship('Questions', secondary='test_questions', backref='tests', lazy='dynamic')
    results = db.relationship('Results', back_populates='test')

class TestQuestions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.testId'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.idQuestion'), nullable=False)

class Questions(db.Model):
    idQuestion = db.Column(db.Integer, primary_key=True)
    Answer = db.Column(db.Text, nullable=False)
    Weight = db.Column(db.Integer, nullable=False)
    Question = db.Column(db.Text, nullable=False)


class EditTestForm(FlaskForm):
    test_name = StringField('Test Name', validators=[DataRequired()])
    selected_questions = SelectMultipleField('Select Questions')
    deleted_questions = SelectMultipleField('Select Questions to Delete')

@app.route('/')
def index():
    with app.app_context():
        db.create_all()
    return render_template('index.html')

@app.route('/view_questions')
def view_questions():
    questions = Questions.query.all()
    return render_template('view_questions.html', questions=questions)

@app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    question = Questions.query.get_or_404(question_id)
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for('view_questions'))


@app.route('/add_question', methods=['GET', 'POST'])
def add_question():
    if request.method == 'POST':
        question_text = request.form.get('question_text')
        answer_text = request.form.get('answer_text')
        weight = request.form.get('weight')

        # Проверяем, что поля вопроса и ответа не пустые
        if not question_text or not answer_text:
            error_message = "Question and Answer cannot be empty."
            return render_template('add_question.html', error_message=error_message)

        # Проверяем, что вес больше 0
        if int(weight) < 1:
            error_message = "Weight must be greater than 0."
            return render_template('add_question.html', error_message=error_message)

        new_question = Questions(Question=question_text, Answer=answer_text, Weight=weight)
        db.session.add(new_question)
        db.session.commit()

        return redirect(url_for('index'))

    return render_template('add_question.html')

@app.route('/create_test', methods=['GET', 'POST'])
def create_test():
    if request.method == 'POST':
        test_name = request.form.get('test_name')
        selected_questions = request.form.getlist('selected_questions')

        if not test_name:
            flash('Test name cannot be empty.', 'error')
            return redirect(url_for('create_test'))

        if not selected_questions:
            flash('Select at least one question to add to the test.', 'error')
            return redirect(url_for('create_test'))

        new_test = Tests(test_name=test_name)

        for question_id in selected_questions:
            question = Questions.query.get_or_404(question_id)
            new_test.questions.append(question)

        db.session.add(new_test)
        db.session.commit()

        flash('Test created successfully.', 'success')
        return redirect(url_for('index'))

    questions = Questions.query.all()
    return render_template('create_test.html', questions=questions)

@app.route('/view_tests')
def view_tests():
    tests = Tests.query.options(joinedload(Tests.results)).all()
    return render_template('view_tests.html', tests=tests)

@app.route('/delete_test/<int:test_id>', methods=['POST'])
def delete_test(test_id):
    test = Tests.query.get_or_404(test_id)

    # Удаляем связанные результаты перед удалением теста
    Results.query.filter_by(test_id=test_id).delete()

    db.session.delete(test)
    db.session.commit()
    return redirect(url_for('view_tests'))

@app.route('/edit_test/<int:test_id>', methods=['GET', 'POST'])
def edit_test(test_id):
    test = Tests.query.get_or_404(test_id)
    questions = Questions.query.all()
    form = EditTestForm()

    if request.method == 'POST':
        # Обработка данных формы

        # Обновление названия теста, если оно было изменено
        new_test_name = request.form.get('test_name')
        if new_test_name and new_test_name != test.test_name:
            test.test_name = new_test_name
            db.session.commit()

        # Добавление новых вопросов к тесту
        selected_questions = request.form.getlist('selected_questions')
        for question_id in selected_questions:
            question = Questions.query.get_or_404(question_id)
            if question not in test.questions:
                test.questions.append(question)
        db.session.commit()

        # Удаление выбранных вопросов из теста
        deleted_questions = request.form.getlist('deleted_questions')
        for question_id in deleted_questions:
            question = Questions.query.get_or_404(question_id)
            if question in test.questions:
                test.questions.remove(question)
        db.session.commit()

        flash('Test updated successfully.', 'success')
        return redirect(url_for('index'))

    return render_template('edit_test.html', test=test, questions=questions, form=form)


@app.route('/take_test', methods=['GET', 'POST'])
def take_test():
    test_id = int(request.form.get("test_selector"))
    selected_test = Tests.query.get_or_404(test_id)
    if request.method == 'POST':

        total_weight = 0
        obtained_weight = 0

        for question in selected_test.questions.all():
            answer_key = 'answer_' + str(question.idQuestion)
            user_answer = request.form.get(answer_key)

            if user_answer is not None:
                total_weight += question.Weight
                if user_answer.lower() == question.Answer.lower():
                    obtained_weight += question.Weight

        # Calculate the score
        score = obtained_weight / total_weight if total_weight != 0 else 0

        # Assign grade based on the score
        if score < 0.5:
            grade = 2
        elif 0.5 <= score < 0.7:
            grade = 3
        elif 0.7 <= score < 0.9:
            grade = 4
        else:
            grade = 5

        # Update the Results table with the test result
        result_entry = Results(result=grade, test_id=test_id)
        db.session.add(result_entry)
        db.session.commit()

        return render_template('test_result.html', grade=grade)  # You can customize this page

    tests = Tests.query.all()
    return render_template('take_test.html', tests=tests, selected_test=selected_test)


if __name__ == '__main__':
    app.run(debug=True)
    # with app.app_context():
    #     db.drop_all()
    #     db.create_all()

